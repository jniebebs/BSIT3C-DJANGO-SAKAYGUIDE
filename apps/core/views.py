from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import connections
from django.db.utils import DatabaseError, OperationalError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from routes.services import fastest_travel_minutes

from .audit import log_account_creation, log_activity
from .commuter_forms import CommuterRegistrationForm
from .permissions import (
    access_denied,
    administrator_required,
    home_url_for,
    is_administrator,
)

User = get_user_model()

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=1)
INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
LOCKED_MESSAGE = 'Too many failed attempts. Locked for 1 minute.'


def _post_login_url(user):
    """Send administrators to the management console, commuters home."""
    return 'management_dashboard' if user.is_staff else 'commuter_dashboard'


def _authenticate_identifier(request, identifier, password):
    """Authenticate with a username or an e-mail address.

    Django's default backend only knows usernames. To avoid revealing which
    accounts exist, a failed e-mail lookup simply falls through to the normal
    username attempt and the generic error message.
    """
    user = authenticate(request, username=identifier, password=password)
    if user is not None or '@' not in identifier:
        return user

    matches = (
        User.objects.filter(email__iexact=identifier)
        .values_list('username', flat=True)[:5]
    )
    for username in matches:
        user = authenticate(request, username=username, password=password)
        if user is not None:
            return user
    return None


def _reset_lock_state(request):
    request.session['failed_attempts'] = 0
    request.session['lock_time'] = None


def _get_lock_state(request):
    failed_attempts = request.session.get('failed_attempts', 0)
    lock_time = request.session.get('lock_time')

    if not lock_time:
        return failed_attempts, None

    try:
        unlock_time = timezone.datetime.fromisoformat(lock_time)
    except (TypeError, ValueError):
        _reset_lock_state(request)
        return 0, None

    if timezone.now() < unlock_time:
        remaining = int((unlock_time - timezone.now()).total_seconds())
        return failed_attempts, remaining

    _reset_lock_state(request)
    return 0, None


def _set_lock_state(request):
    lock_until = timezone.now() + LOCK_DURATION
    request.session['failed_attempts'] = MAX_FAILED_ATTEMPTS
    request.session['lock_time'] = lock_until.isoformat()
    return int(LOCK_DURATION.total_seconds())


def _validate_registration_data(data):
    errors = {}

    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not username:
        errors['username'] = 'Username is required.'
    elif User.objects.filter(username=username).exists():
        errors['username'] = 'Username already taken.'

    if not first_name:
        errors['first_name'] = 'First name is required.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'

    if not email:
        errors['email'] = 'Email is required.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
        else:
            if User.objects.filter(email=email).exists():
                errors['email'] = 'Email already registered.'

    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters.'
    else:
        try:
            validate_password(password)
        except ValidationError as exc:
            errors['password'] = ' '.join(exc.messages)

    if password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    return errors


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_post_login_url(request.user))

    failed_attempts, remaining = _get_lock_state(request)
    if remaining is not None:
        messages.error(request, f'Too many failed attempts. Try again in {remaining} seconds.')
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    if request.method == 'GET':
        return render(request, 'auth/login.html')

    identifier = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = _authenticate_identifier(request, identifier, password)

    if user is not None:
        _reset_lock_state(request)
        login(request, user)
        log_activity(
            user,
            'LOGIN',
            'auth_user',
            record_id=user.pk,
            description=(
                f'{user.username} signed in to the '
                f'{"management console" if user.is_staff else "commuter dashboard"}.'
            ),
        )
        return redirect(_post_login_url(user))

    failed_attempts += 1
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request)
        messages.error(request, LOCKED_MESSAGE)
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html')


@require_POST
def logout_view(request):
    user = request.user if request.user.is_authenticated else None
    if user is not None:
        log_activity(
            user,
            'LOGOUT',
            'auth_user',
            record_id=user.pk,
            description=f'{user.username} signed out.',
        )
    logout(request)
    messages.info(request, 'You have been signed out securely.')
    return redirect('login')


# ---------------------------------------------------------------------------
# Role specific sign-in portals
# ---------------------------------------------------------------------------

def _portal_context(request, role, banner=None):
    """Shared context for the administrator and commuter sign-in pages."""
    return {
        'locked': False,
        'remaining': None,
        'identifier': request.POST.get('username', '').strip(),
        'role': role,
        'banner': banner,
    }


def _sign_in(request, role, template, banner=None):
    """Sign-in flow shared by the administrator and commuter portals.

    ``role`` is either ``'administrator'`` or ``'commuter'``. An account can
    only sign in on the portal that matches its own role, which keeps the two
    account experiences completely separate. A wrong-portal attempt is not
    counted as a failed password attempt, so one account can never lock
    another one out.
    """
    if request.user.is_authenticated:
        return redirect(_post_login_url(request.user))

    failed_attempts, remaining = _get_lock_state(request)
    if remaining is not None:
        messages.error(
            request,
            f'Too many failed attempts. Try again in {remaining} seconds.',
        )
        context = _portal_context(request, role, banner)
        context.update({'locked': True, 'remaining': remaining})
        return render(request, template, context)

    if request.method == 'GET':
        return render(
            request, template, _portal_context(request, role, banner)
        )

    identifier = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = _authenticate_identifier(request, identifier, password)

    if user is not None and not user.is_active:
        # A deactivated account must never get a session.
        user = None

    if user is not None:
        if role == 'administrator' and not is_administrator(user):
            messages.error(
                request,
                'That is not an administrator account. Use the commuter '
                'sign-in page instead.',
            )
            return render(
                request, template, _portal_context(request, role, banner)
            )
        if role == 'commuter' and is_administrator(user):
            messages.error(
                request,
                'Administrator accounts sign in on the administrator page.',
            )
            return render(
                request, template, _portal_context(request, role, banner)
            )

        _reset_lock_state(request)
        login(request, user)
        log_activity(
            user,
            'LOGIN',
            'auth_user',
            record_id=user.pk,
            description=(
                f'{user.username} signed in to the '
                f'{"management console" if user.is_staff else "commuter dashboard"}.'
            ),
        )
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect(_post_login_url(user))

    failed_attempts += 1
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request)
        messages.error(request, LOCKED_MESSAGE)
        context = _portal_context(request, role, banner)
        context.update({'locked': True, 'remaining': remaining})
        return render(request, template, context)

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(
        request,
        f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.',
    )
    return render(request, template, _portal_context(request, role, banner))


@require_http_methods(['GET', 'POST'])
def admin_login_view(request):
    """Administrator sign-in page.

    Only staff accounts can get a session here. Commuters are told to use the
    commuter portal instead of being shown a raw error page, and an already
    signed-in commuter is refused the page entirely: the administrator
    sign-in interface is not part of the commuter experience.
    """
    if request.user.is_authenticated:
        if is_administrator(request.user):
            return redirect('management_dashboard')
        return access_denied(
            request,
            'The administrator sign-in page is not available to commuter accounts.',
            'Commuters use the commuter sign-in page to reach Find My Route, '
            'Google Maps and their own profile.',
        )

    return _sign_in(
        request,
        'administrator',
        'auth/admin_login.html',
        banner=(
            'Administrator accounts manage locations, routes, stops, fares, '
            'commuter accounts and the Google Maps registry.'
        ),
    )


@require_http_methods(['GET', 'POST'])
def commuter_login_view(request):
    """Commuter sign-in page.

    Only non-staff commuter accounts can get a session here. An already
    signed-in administrator is sent to the administrator sign-in page.
    """
    if request.user.is_authenticated:
        if is_administrator(request.user):
            return redirect('admin_login')
        return redirect('commuter_dashboard')

    return _sign_in(
        request,
        'commuter',
        'auth/commuter_login.html',
        banner=(
            'Commuter accounts find jeepney, bus and tricycle routes, check '
            'estimated fares and travel times, and use live GPS directions.'
        ),
    )


def _sakayguide_stats(log_limit=6, recent_search_limit=5):
    """Collect dashboard statistics from the SakayGuide transit database."""
    log_limit = max(0, min(int(log_limit), 200))
    recent_search_limit = max(0, min(int(recent_search_limit), 200))
    stats = {}
    with connections['sakayguide'].cursor() as cursor:
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM routes WHERE status = 'active'),
                (SELECT COUNT(*) FROM route_stops),
                (SELECT COUNT(*) FROM locations WHERE status = 'active'),
                (SELECT COUNT(*) FROM barangays),
                (SELECT COUNT(*) FROM route_transfers),
                (SELECT COUNT(*) FROM route_fares WHERE status = 'active'),
                (SELECT COUNT(*) FROM users WHERE role = 'commuter' AND status = 'active'),
                (SELECT COUNT(*) FROM saved_routes),
                (SELECT COUNT(*) FROM search_history),
                (SELECT COUNT(*) FROM route_landmarks),
                (SELECT COUNT(*) FROM locations WHERE status = 'inactive'),
                (SELECT COUNT(*) FROM transportation_types WHERE status = 'active')
            """
        )
        row = cursor.fetchone()
        keys = (
            'active_routes', 'route_stops', 'active_locations', 'barangays',
            'transfers', 'active_fares', 'commuters', 'saved_routes',
            'searches', 'landmarks', 'inactive_locations', 'transport_types',
        )
        stats.update(dict(zip(keys, row)))

        cursor.execute(
            """
            SELECT municipality_name, province
            FROM municipalities
            WHERE status = 'active'
            ORDER BY municipality_id
            LIMIT 1
            """
        )
        municipality = cursor.fetchone()
        stats['municipality'] = (
            {'name': municipality[0], 'province': municipality[1]}
            if municipality else None
        )

        cursor.execute(
            """
            SELECT r.route_code, r.route_name, tt.transport_name,
                   o.location_name AS origin_name,
                   d.location_name AS destination_name,
                   r.estimated_travel_time,
                   (SELECT COUNT(*) FROM route_stops rs WHERE rs.route_id = r.route_id) AS stop_count,
                   (SELECT MIN(f.total_estimated_fare)
                      FROM route_fares f
                     WHERE f.route_id = r.route_id AND f.status = 'active') AS min_fare
              FROM routes r
              JOIN transportation_types tt ON tt.transport_type_id = r.transport_type_id
              JOIN locations o ON o.location_id = r.origin_id
              JOIN locations d ON d.location_id = r.destination_id
             WHERE r.status = 'active'
             ORDER BY r.route_code
            """
        )
        stats['routes'] = [
            {
                'code': row[0], 'name': row[1], 'transport': row[2],
                'origin': row[3], 'destination': row[4],
                'travel_time': row[5], 'stops': row[6], 'min_fare': row[7],
            }
            for row in cursor.fetchall()
        ]

        cursor.execute(
            """
            SELECT fr.route_code, tr.route_code, l.location_name,
                   t.estimated_transfer_time, t.additional_estimated_fare
              FROM route_transfers t
              JOIN routes fr ON fr.route_id = t.from_route_id
              JOIN routes tr ON tr.route_id = t.to_route_id
              JOIN locations l ON l.location_id = t.transfer_location_id
             ORDER BY t.transfer_id
            """
        )
        stats['transfer_list'] = [
            {
                'from_code': row[0], 'to_code': row[1], 'location': row[2],
                'time': row[3], 'fare': row[4],
            }
            for row in cursor.fetchall()
        ]

        cursor.execute(
            """
            SELECT tt.transport_name, COUNT(r.route_id)
              FROM transportation_types tt
              LEFT JOIN routes r
                ON r.transport_type_id = tt.transport_type_id
               AND r.status = 'active'
             WHERE tt.status = 'active'
             GROUP BY tt.transport_type_id, tt.transport_name
             ORDER BY tt.transport_type_id
            """
        )
        total_routes = stats['active_routes'] or 0
        stats['transport_breakdown'] = [
            {
                'name': name,
                'count': count,
                'percent': round(count * 100 / total_routes) if total_routes else 0,
            }
            for name, count in cursor.fetchall()
        ]

        if log_limit:
            cursor.execute(
                f"""
                SELECT u.full_name, a.action_type, a.table_affected,
                       a.action_description, a.created_at
                  FROM admin_activity_logs a
                  JOIN users u ON u.user_id = a.admin_id
                 ORDER BY a.created_at DESC, a.log_id DESC
                 LIMIT {log_limit}
                """
            )
            stats['recent_logs'] = [
                {
                    'admin': row[0], 'action': row[1], 'table': row[2],
                    'description': row[3], 'created_at': row[4],
                }
                for row in cursor.fetchall()
            ]
        else:
            stats['recent_logs'] = []

        cursor.execute(
            """
            SELECT l.location_name, l.location_type, b.barangay_name,
                   (l.latitude IS NOT NULL AND l.longitude IS NOT NULL)
              FROM locations l
              JOIN barangays b ON b.barangay_id = l.barangay_id
             WHERE l.status = 'active'
             ORDER BY l.location_name
            """
        )
        stats['location_list'] = [
            {
                'name': row[0], 'type': row[1], 'barangay': row[2],
                'has_coords': bool(row[3]),
            }
            for row in cursor.fetchall()
        ]

        # ---- Search analytics (last 7 days) ---------------------------------
        today = timezone.localdate()
        week_start = today - timedelta(days=6)
        previous_week_start = week_start - timedelta(days=7)

        cursor.execute(
            """
            SELECT DATE(search_date), COUNT(*)
              FROM search_history
             WHERE search_date >= %s
             GROUP BY DATE(search_date)
             ORDER BY DATE(search_date)
            """,
            [week_start],
        )
        daily_counts = {row[0]: row[1] for row in cursor.fetchall()}
        activity = []
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            activity.append({
                'date': day.isoformat(),
                'label': day.strftime('%a'),
                'full_label': day.strftime('%b %d'),
                'count': daily_counts.get(day, 0),
            })
        stats['search_activity'] = activity
        stats['search_week_total'] = sum(item['count'] for item in activity)
        busiest_day = max(activity, key=lambda item: item['count'])
        stats['busiest_day'] = busiest_day if busiest_day['count'] else None

        cursor.execute(
            """
            SELECT COUNT(*)
              FROM search_history
             WHERE search_date >= %s AND search_date < %s
            """,
            [previous_week_start, week_start],
        )
        stats['search_previous_week_total'] = cursor.fetchone()[0] or 0
        if stats['search_previous_week_total'] >= 10:
            stats['search_week_change'] = round(
                (stats['search_week_total']
                 - stats['search_previous_week_total'])
                * 100 / stats['search_previous_week_total']
            )
        elif stats['search_week_total']:
            # Too little history to make a meaningful percentage comparison.
            stats['search_week_change'] = None
        else:
            stats['search_week_change'] = 0

        cursor.execute(
            """
            SELECT l.location_name, COUNT(*) AS hits
              FROM search_history sh
              JOIN locations l ON l.location_id = sh.destination_id
             GROUP BY l.location_id, l.location_name
             ORDER BY hits DESC, l.location_name
             LIMIT 5
            """
        )
        destination_rows = cursor.fetchall()
        top_hits = destination_rows[0][1] if destination_rows else 0
        total_searches = stats['searches'] or 0
        stats['top_destinations'] = [
            {
                'name': name,
                'count': count,
                'share': (
                    round(count * 100 / total_searches)
                    if total_searches else 0
                ),
                'bar': round(count * 100 / top_hits) if top_hits else 0,
            }
            for name, count in destination_rows
        ]

        # ---- Top origins (mirror of top destinations) ------------------------
        cursor.execute(
            """
            SELECT l.location_name, COUNT(*) AS hits
              FROM search_history sh
              JOIN locations l ON l.location_id = sh.origin_id
             GROUP BY l.location_id, l.location_name
             ORDER BY hits DESC, l.location_name
             LIMIT 5
            """
        )
        origin_rows = cursor.fetchall()
        origin_top_hits = origin_rows[0][1] if origin_rows else 0
        stats['top_origins'] = [
            {
                'name': name,
                'count': count,
                'share': (
                    round(count * 100 / total_searches)
                    if total_searches else 0
                ),
                'bar': round(count * 100 / origin_top_hits) if origin_top_hits else 0,
            }
            for name, count in origin_rows
        ]

        if recent_search_limit:
            cursor.execute(
                f"""
                SELECT COALESCE(u.full_name, 'Guest'),
                       sh.origin_id, o.location_name,
                       sh.destination_id, d.location_name,
                       sh.search_date
                  FROM search_history sh
                  JOIN locations o ON o.location_id = sh.origin_id
                  JOIN locations d ON d.location_id = sh.destination_id
                  LEFT JOIN users u ON u.user_id = sh.user_id
                 ORDER BY sh.search_date DESC, sh.search_id DESC
                 LIMIT {recent_search_limit}
                """
            )
            minute_cache = {}
            recent_searches = []
            for row in cursor.fetchall():
                pair = (row[1], row[3])
                if pair not in minute_cache:
                    minute_cache[pair] = fastest_travel_minutes(*pair)
                recent_searches.append({
                    'user': row[0],
                    'origin': row[2],
                    'destination': row[4],
                    'searched_at': row[5],
                    'minutes': minute_cache[pair],
                })
            stats['recent_searches'] = recent_searches
        else:
            stats['recent_searches'] = []

        cursor.execute(
            """
            SELECT u.user_id, u.full_name, u.email, u.status, u.created_at,
                   (SELECT COUNT(*)
                      FROM search_history sh
                     WHERE sh.user_id = u.user_id) AS search_count,
                   (SELECT COUNT(*)
                      FROM saved_routes sr
                     WHERE sr.user_id = u.user_id) AS saved_count,
                   (SELECT MAX(sh.search_date)
                      FROM search_history sh
                     WHERE sh.user_id = u.user_id) AS last_search
              FROM users u
             WHERE u.role = 'commuter'
             ORDER BY u.created_at DESC, u.user_id DESC
            """
        )
        stats['commuter_list'] = [
            {
                'user_id': row[0],
                'name': row[1] or 'Unnamed commuter',
                'email': row[2] or '',
                'status': row[3],
                'created_at': row[4],
                'searches': row[5],
                'saved_routes': row[6],
                'last_search': row[7],
            }
            for row in cursor.fetchall()
        ]
        stats['inactive_commuters'] = max(
            0, len(stats['commuter_list']) - (stats['commuters'] or 0)
        )
        stats['new_commuters_week'] = sum(
            1 for commuter in stats['commuter_list']
            if commuter['created_at']
            and commuter['created_at'].date() >= week_start
        )

        # ---- Network / data completeness ------------------------------------
        cursor.execute(
            """
            SELECT MIN(total_estimated_fare), MAX(total_estimated_fare),
                   AVG(total_estimated_fare)
              FROM route_fares
             WHERE status = 'active'
            """
        )
        fare_min, fare_max, fare_average = cursor.fetchone()
        stats['fare_min'] = fare_min
        stats['fare_max'] = fare_max
        stats['fare_average'] = (
            round(fare_average, 2) if fare_average is not None else None
        )

        cursor.execute(
            """
            SELECT COUNT(*)
              FROM locations
             WHERE status = 'active'
               AND latitude IS NOT NULL
               AND longitude IS NOT NULL
            """
        )
        stats['active_with_coords'] = cursor.fetchone()[0] or 0
        stats['coverage_percent'] = (
            round(stats['active_with_coords'] * 100 / stats['active_locations'])
            if stats['active_locations'] else 0
        )

        # ---- Network health / data completeness -----------------------------
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*)
                   FROM routes r
                  WHERE r.status = 'active'
                    AND NOT EXISTS (SELECT 1 FROM route_stops s
                                     WHERE s.route_id = r.route_id)) AS routes_without_stops,
                (SELECT COUNT(*)
                   FROM routes r
                  WHERE r.status = 'active'
                    AND NOT EXISTS (SELECT 1 FROM route_fares f
                                     WHERE f.route_id = r.route_id
                                       AND f.status = 'active')) AS routes_without_fares,
                (SELECT COUNT(*)
                   FROM routes r
                  WHERE r.status = 'active'
                    AND NOT EXISTS (SELECT 1 FROM route_transfers t
                                     WHERE t.from_route_id = r.route_id
                                        OR t.to_route_id = r.route_id)) AS routes_without_transfers,
                (SELECT AVG(estimated_travel_time)
                   FROM routes WHERE status = 'active') AS avg_travel_time,
                (SELECT MIN(estimated_travel_time)
                   FROM routes WHERE status = 'active') AS min_travel_time,
                (SELECT MAX(estimated_travel_time)
                   FROM routes WHERE status = 'active') AS max_travel_time
            """
        )
        (
            routes_without_stops,
            routes_without_fares,
            routes_without_transfers,
            avg_travel_time,
            min_travel_time,
            max_travel_time,
        ) = cursor.fetchone()

        stats['routes_without_stops'] = routes_without_stops or 0
        stats['routes_without_fares'] = routes_without_fares or 0
        stats['routes_without_transfers'] = routes_without_transfers or 0
        stats['avg_travel_time'] = (
            round(avg_travel_time, 1) if avg_travel_time is not None else None
        )
        stats['min_travel_time'] = min_travel_time
        stats['max_travel_time'] = max_travel_time

        route_total = stats['active_routes'] or 0
        location_total = stats['active_locations'] or 0

        def _ratio(ok, total):
            return round(ok * 100 / total) if total else 0

        health_checks = [
            {
                'key': 'stops',
                'label': 'Routes with ordered stops',
                'detail': (
                    f"{route_total - stats['routes_without_stops']}"
                    f" of {route_total} routes"
                ),
                'percent': _ratio(
                    route_total - stats['routes_without_stops'], route_total
                ),
                'icon': 'fa-circle-stop',
            },
            {
                'key': 'fares',
                'label': 'Routes with an active fare',
                'detail': (
                    f"{route_total - stats['routes_without_fares']}"
                    f" of {route_total} routes"
                ),
                'percent': _ratio(
                    route_total - stats['routes_without_fares'], route_total
                ),
                'icon': 'fa-ticket',
            },
            {
                'key': 'coords',
                'label': 'Locations with verified coordinates',
                'detail': (
                    f"{stats['active_with_coords']} of {location_total} locations"
                ),
                'percent': stats['coverage_percent'],
                'icon': 'fa-map-pin',
            },
        ]
        stats['health_checks'] = health_checks
        stats['network_health'] = (
            round(sum(check['percent'] for check in health_checks) / len(health_checks))
            if health_checks else 0
        )

        cursor.execute(
            "SELECT COUNT(*) FROM admin_activity_logs WHERE created_at >= %s",
            [week_start],
        )
        stats['activity_this_week'] = cursor.fetchone()[0] or 0

    return stats


def _dashboard_page(request, template_name, **stats_options):
    """Render a dashboard page from the shared SakayGuide statistics."""
    stats = None
    error = None
    try:
        stats = _sakayguide_stats(**stats_options)
    except (OperationalError, DatabaseError) as exc:
        error = (
            'Could not connect to the SakayGuide database '
            '(sakayguide_db). Start MySQL/XAMPP and try again. '
            f'({exc.__class__.__name__})'
        )
    return render(
        request,
        template_name,
        {
            'stats': stats,
            'db_error': error,
            'generated_at': timezone.now(),
        },
    )


@administrator_required
def home(request):
    return _dashboard_page(
        request,
        'home.html',
        log_limit=6,
        recent_search_limit=0,
    )


@administrator_required
def activity(request):
    return _dashboard_page(
        request,
        'dashboard/activity.html',
        log_limit=40,
        recent_search_limit=0,
    )


@administrator_required
def active_routes(request):
    return _dashboard_page(
        request,
        'dashboard/routes.html',
        log_limit=0,
        recent_search_limit=0,
    )


@administrator_required
def active_locations(request):
    return _dashboard_page(
        request,
        'dashboard/locations.html',
        log_limit=0,
        recent_search_limit=0,
    )


@administrator_required
def transfer_links(request):
    return _dashboard_page(
        request,
        'dashboard/transfers.html',
        log_limit=0,
        recent_search_limit=0,
    )


@administrator_required
def commuters(request):
    return _dashboard_page(
        request,
        'dashboard/commuters.html',
        log_limit=0,
        recent_search_limit=20,
    )


@require_http_methods(['GET', 'POST'])
def register_view(request):
    """Commuter self-registration.

    The commuter role is always assigned: the form has no role field, so a
    crafted POST can never ask for administrator privileges. The legacy
    ``/register/`` URL keeps working and renders the same page as
    ``/commuter/register/``.
    """
    if request.user.is_authenticated:
        return redirect(_post_login_url(request.user))

    form = CommuterRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        log_account_creation(
            actor=user,
            account=user,
            account_role='commuter',
            description=(
                f'Self-registered commuter account "{user.username}" '
                f'({user.email}) was created.'
            ),
        )
        login(request, user)
        messages.success(
            request,
            'Welcome to SakayGuide! Your commuter account is ready.',
        )
        return redirect('commuter_dashboard')

    return render(request, 'auth/commuter_register.html', {'form': form})
