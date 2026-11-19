"""Views for the SakayGuide commuter account area.

Commuters use these pages to plan journeys, review their own searches and
manage their own profile. They can never reach the transit records or the
administrator console: every view is protected by ``commuter_required`` and
the forms never expose a role, activation or permission field.

The transit data itself stays in the ``sakayguide`` database, so every query
below is served by the SakayGuide database router.
"""
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.db import DatabaseError
from django.shortcuts import redirect, render

from routes.models import (
    Location,
    Route,
    SavedRoute,
    SearchHistory,
    TransportationType,
)
from routes.services import (
    fares_version,
    popular_destinations,
    transport_options,
)

from .audit import log_activity, sakay_user_for
from .commuter_forms import CommuterPasswordForm, CommuterProfileForm
from .permissions import commuter_required

RECENT_SEARCH_LIMIT = 6
SAVED_ROUTE_LIMIT = 6


def _commuter_row(user):
    """Return the SakayGuide mirror row for a commuter, or ``None``.

    The mirror lives in ``sakayguide_db.users`` and is what the saved-route
    and search-history tables point at. It is created on demand, so a fresh
    commuter account works straight away.
    """
    try:
        return sakay_user_for(user, role='commuter')
    except DatabaseError:
        return None


def _recent_searches(user, limit=RECENT_SEARCH_LIMIT):
    """The signed-in commuter's own recent route searches."""
    row = _commuter_row(user)
    if row is None:
        return []
    entries = (
        SearchHistory.objects.filter(user=row)
        .select_related('origin', 'destination')
        .order_by('-search_date', '-search_id')[:limit]
    )
    return [
        {
            'origin': entry.origin.location_name,
            'origin_id': entry.origin_id,
            'destination': entry.destination.location_name,
            'destination_id': entry.destination_id,
            'searched_at': entry.search_date,
        }
        for entry in entries
    ]


def _saved_routes(user, limit=SAVED_ROUTE_LIMIT):
    """The routes this commuter saved for later."""
    row = _commuter_row(user)
    if row is None:
        return []
    entries = (
        SavedRoute.objects.filter(user=row)
        .select_related('origin', 'destination')
        .order_by('-saved_at')[:limit]
    )
    return [
        {
            'nickname': entry.nickname,
            'origin': entry.origin.location_name,
            'origin_id': entry.origin_id,
            'destination': entry.destination.location_name,
            'destination_id': entry.destination_id,
            'saved_at': entry.saved_at,
        }
        for entry in entries
    ]


def _network_snapshot():
    """Small counts shown on the commuter dashboard."""
    try:
        return {
            'active_routes': Route.objects.filter(status='active').count(),
            'active_locations': Location.objects.filter(
                status='active'
            ).count(),
            'transport_modes': TransportationType.objects.filter(
                status='active'
            ).count(),
            'connected': True,
        }
    except DatabaseError:
        return {
            'active_routes': 0,
            'active_locations': 0,
            'transport_modes': 0,
            'connected': False,
        }


@commuter_required
def dashboard(request):
    """The commuter home page.

    Shows a welcome message, a prominent Find My Route shortcut, the
    commuter's own recent searches, the most popular destinations and the
    transport options that are currently active.
    """
    snapshot = _network_snapshot()

    try:
        options = transport_options()
        popular = popular_destinations(limit=6)
        fare_version = fares_version()
    except DatabaseError:
        options, popular, fare_version = [], [], ''

    jeepney = [
        option for option in options
        if 'jeep' in option['transport_key']
    ]
    tricycle = [
        option for option in options
        if 'tricycle' in option['transport_key']
    ]
    bus = [
        option for option in options
        if 'bus' in option['transport_key']
    ]
    featured = jeepney + tricycle + bus

    return render(request, 'commuter/dashboard.html', {
        'snapshot': snapshot,
        'options': options,
        'jeepney_options': jeepney,
        'tricycle_options': tricycle,
        'bus_options': bus,
        'other_options': [
            option for option in options
            if option not in featured
        ],
        'popular': popular,
        'recent_searches': _recent_searches(request.user),
        'saved_routes': _saved_routes(request.user),
        'fare_version': fare_version,
        'fare_autoreload': True,
    })


@commuter_required
def recent_searches(request):
    """The commuter's own route-search history.

    The list is read-only: a commuter can re-run a journey they searched
    before, but they can never edit or delete a search record or any
    transportation record from this page.
    """
    return render(request, 'commuter/recent_searches.html', {
        'recent_searches': _recent_searches(request.user, limit=40),
        'saved_routes': _saved_routes(request.user),
    })


@commuter_required
def profile(request):
    """View and edit the commuter's own profile.

    The form only exposes name, username and e-mail. Role, activation and
    permission flags are never part of it, so a commuter can neither promote
    themselves nor re-activate a suspended account.
    """
    user = request.user
    recent = _recent_searches(user, limit=8)

    if request.method == 'POST':
        form = CommuterProfileForm(request.POST, instance=user, actor=user)
        if form.is_valid():
            form.save()
            log_activity(
                user,
                'UPDATE',
                'auth_user',
                record_id=user.pk,
                description=f'{user.username} updated their commuter profile.',
            )
            messages.success(request, 'Your profile was updated.')
            return redirect('commuter_profile')
    else:
        form = CommuterProfileForm(instance=user, actor=user)

    return render(request, 'commuter/profile.html', {
        'form': form,
        'recent_searches': recent,
        'saved_routes': _saved_routes(user),
    })


@commuter_required
def password_change(request):
    """Let a commuter change their own password."""
    user = request.user

    if request.method == 'POST':
        form = CommuterPasswordForm(request.POST, actor=user)
        if form.is_valid():
            form.save(user)
            # Keep the current session valid after the password changes.
            update_session_auth_hash(request, user)
            log_activity(
                user,
                'UPDATE',
                'auth_user',
                record_id=user.pk,
                description=f'{user.username} changed their password.',
            )
            messages.success(request, 'Your password was changed.')
            return redirect('commuter_profile')
    else:
        form = CommuterPasswordForm(actor=user)

    return render(request, 'commuter/password.html', {'form': form})
