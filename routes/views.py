from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render, reverse
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_POST

from .forms import RouteSearchForm, SaveRouteForm
from .models import Location, SakayUser, SavedRoute, SearchHistory
from .services import (
    find_journeys,
    location_choices,
    locations_map,
    popular_destinations,
    sort_journeys,
)

PROVISIONAL_NOTE = (
    'Routes, fares, travel times and transfers shown here are provisional '
    'test estimates from the SakayGuide database - not official transport '
    'information.'
)


def _resolve_location(location_id):
    """Return an active Location for a raw id, or None."""
    if not location_id:
        return None
    try:
        return Location.objects.get(pk=location_id, status='active')
    except (Location.DoesNotExist, TypeError, ValueError):
        return None


def _sakay_user_for(django_user):
    """Map a Django auth user to the sakayguide_db ``users`` row.

    The saved_routes/search_history tables reference ``users.user_id`` from
    the SakayGuide database, so each logged-in Django user gets a mirror row
    (matched by e-mail first). Authentication itself stays in Django.
    """
    if not django_user.is_authenticated:
        return None

    email = (django_user.email or '').strip().lower()
    if email:
        existing = SakayUser.objects.filter(email=email).first()
        if existing:
            return existing

    mirror_email = email or f'user{django_user.pk}@sakayguide.local'
    try:
        with transaction.atomic():
            return SakayUser.objects.create(
                full_name=django_user.get_full_name() or django_user.username,
                email=mirror_email,
                # Opaque stored value; real login uses Django's hashers.
                password=f'unused-{get_random_string(32)}',
                role=SakayUser.ROLE_COMMUTER,
                status='active',
            )
    except IntegrityError:
        return SakayUser.objects.get(email=mirror_email)


def _record_search(user, origin, destination):
    """Save the search in search_history (guest searches keep user NULL)."""
    with transaction.atomic():
        SearchHistory.objects.create(
            user=_sakay_user_for(user),
            origin=origin,
            destination=destination,
        )


def route_search(request):
    """Main 'Where do you want to go?' page (search + results)."""
    # Treat the form as bound only when a location was actually submitted,
    # so visiting /plan/?sort=fare shows the clean search page.
    bound = bool(request.GET.get('origin') or request.GET.get('destination'))
    form = RouteSearchForm(request.GET if bound else None)

    journeys = []
    searched = False
    origin = destination = None
    sort = 'fare'
    maps = []

    if bound and form.is_valid():
        searched = True
        sort = form.cleaned_data.get('sort') or 'fare'
        origin = _resolve_location(form.cleaned_data['origin'])
        destination = _resolve_location(form.cleaned_data['destination'])

        if origin and destination:
            journeys = find_journeys(
                origin.location_id, destination.location_id,
                origin=origin, destination=destination,
            )
            journeys = sort_journeys(journeys, sort)
            if journeys:
                maps = [journey['map'] for journey in journeys]
            else:
                # No route: still show the Kabankalan City map.
                maps = [locations_map(origin, destination)]
            try:
                _record_search(request.user, origin, destination)
            except Exception:  # pragma: no cover - history must not break search
                pass

    context = {
        'form': form,
        'locations': location_choices(),
        'popular': popular_destinations(),
        'provisional_note': PROVISIONAL_NOTE,
        'searched': searched,
        'origin': origin,
        'destination': destination,
        'journeys': journeys,
        'maps': maps,
        'sort': sort,
        'sort_choices': [
            ('fare', 'Lowest fare'),
            ('time', 'Shortest time'),
            ('transfers', 'Fewest transfers'),
        ],
    }

    template = 'routes/route_results.html' if searched else 'routes/route_search.html'
    return render(request, template, context)


@require_POST
@login_required(login_url='login')
def save_route(request):
    """Save an origin -> destination pair for the signed-in user."""
    form = SaveRouteForm(request.POST)
    referer = request.META.get('HTTP_REFERER') or reverse('routes:route_search')

    if not form.is_valid():
        messages.error(request, 'Could not save that route. Please try again.')
        return redirect(referer)

    origin_id = form.cleaned_data['origin']
    destination_id = form.cleaned_data['destination']
    nickname = form.cleaned_data.get('nickname') or None

    with transaction.atomic():
        sakay_user = _sakay_user_for(request.user)
        existing = SavedRoute.objects.filter(
            user=sakay_user, origin_id=origin_id, destination_id=destination_id,
        ).first()

        if existing:
            if nickname and nickname != existing.nickname:
                existing.nickname = nickname
                existing.save(update_fields=['nickname'])
            created = False
        else:
            SavedRoute.objects.create(
                user=sakay_user,
                origin_id=origin_id,
                destination_id=destination_id,
                nickname=nickname,
            )
            created = True

    if created:
        messages.success(request, 'Route saved to your account.')
    else:
        messages.info(request, 'That route is already in your saved routes.')

    search_url = reverse('routes:route_search')
    return redirect(
        f'{search_url}?origin={origin_id}&destination={destination_id}&sort={form.data.get("sort", "fare")}'
    )
