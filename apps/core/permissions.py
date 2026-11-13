"""Access-control helpers for the SakayGuide platform.

SakayGuide has two completely separate account experiences:

``administrator``
    A Django staff account. Manages locations, routes, stops, fares, transfers,
    commuter accounts, the Google Maps registry and the system audit trail.
    Administrators never get the commuter navigation interface.

``commuter``
    An ordinary Django account. Uses Find My Route, Google Maps, live GPS,
    the travel guide, estimated fares and estimated travel times. Commuters
    never get the management screens.

The single role flag is ``User.is_staff``. Every staff account is an
administrator with full management permissions; ordinary accounts never are:
self-registration always creates a plain user, and no public form exposes a
role field. There is no separate super administrator role.

Rules enforced here:

* Anonymous visitors are redirected to the sign-in page of the area they
  tried to reach.
* Signed-in users of the wrong role receive an HTTP 403 with the styled
  access-denied page. The check is server side, so hiding a link is never
  the only protection.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def is_administrator(user):
    """Return True for an active Django staff account.

    ``is_staff`` is the single role flag that grants access to the custom
    management dashboard. Accounts that were originally created as Django
    superusers are administrators like every other staff account, so they
    keep their account and their permissions.
    """
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.is_staff
    )


def is_commuter(user):
    """Return True for an active signed-in account that is not an administrator.

    Administrators are excluded on purpose: an administrator session must
    never be able to reach commuter-only pages and inherit navigation
    behaviour.
    """
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and not user.is_staff
    )


def home_url_for(user):
    """Return the landing page URL name for a signed-in user."""
    if is_administrator(user):
        return 'management_dashboard'
    return 'commuter_dashboard'


def login_url_for(user):
    """Return the sign-in page URL name that matches a user's role."""
    if is_administrator(user):
        return 'admin_login'
    return 'commuter_login'


def access_denied(request, message, detail=None):
    """Render the styled HTTP 403 access-denied page.

    The page explains which area the visitor tried to reach and links to the
    sign-in page that belongs to it, so the visitor is never left at a bare
    "403 Forbidden" error.
    """
    context = {
        'message': message,
        'detail': detail,
        'login_url_name': (
            'admin_login' if request.user.is_authenticated
            and is_administrator(request.user)
            else 'commuter_login'
        ),
    }
    return render(request, '403.html', context, status=403)


def administrator_required(view_func):
    """Protect a view with login + staff-role checks.

    Unauthenticated visitors are sent to the administrator sign-in page.
    Signed-in commuters receive HTTP 403 with the access-denied page, so a
    commuter can never read or change transit records.
    """

    @login_required(login_url='admin_login')
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_administrator(request.user):
            return access_denied(
                request,
                'Administrator access is required for that page.',
                'This area manages locations, routes, fares and accounts. '
                'Commuter accounts can use Find My Route and their own profile.',
            )
        return view_func(request, *args, **kwargs)

    return _wrapped


def commuter_required(view_func):
    """Protect a view so only commuter accounts can open it.

    Administrators receive HTTP 403 with the access-denied page: the
    Find My Route, Google Maps and live GPS navigation screens belong to
    commuters only.
    """

    @login_required(login_url='commuter_login')
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if is_administrator(request.user):
            return access_denied(
                request,
                'This page is part of the commuter navigation experience.',
                'Administrators manage the transportation records from the '
                'administration console instead of using the live commuter '
                'navigation interface.',
            )
        return view_func(request, *args, **kwargs)

    return _wrapped


# Backwards compatible alias: the commuter-only guard used by the Find My
# Route feature.
commuter_only = commuter_required
