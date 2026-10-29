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
from django.views.decorators.http import require_http_methods

from routes.services import fastest_travel_minutes

from .audit import log_account_creation

User = get_user_model()

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=1)
INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
LOCKED_MESSAGE = 'Too many failed attempts. Locked for 1 minute.'


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
        return redirect('dashboard')

    failed_attempts, remaining = _get_lock_state(request)
    if remaining is not None:
        messages.error(request, f'Too many failed attempts. Try again in {remaining} seconds.')
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    if request.method == 'GET':
        return render(request, 'auth/login.html')

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = authenticate(request, username=username, password=password)

    if user is not None:
        _reset_lock_state(request)
        login(request, user)
        return redirect('dashboard')

    failed_attempts += 1
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request)
        messages.error(request, LOCKED_MESSAGE)
        return render(request, 'auth/login.html', {'locked': True, 'remaining': remaining})

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def _sakayguide_stats():
    """Collect dashboard statistics from the SakayGuide transit database."""
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

        cursor.execute(
            """
            SELECT u.full_name, a.action_type, a.table_affected,
                   a.action_description, a.created_at
              FROM admin_activity_logs a
              JOIN users u ON u.user_id = a.admin_id
             ORDER BY a.created_at DESC, a.log_id DESC
             LIMIT 6
            """
        )
        stats['recent_logs'] = [
            {
                'admin': row[0], 'action': row[1], 'table': row[2],
                'description': row[3], 'created_at': row[4],
            }
            for row in cursor.fetchall()
        ]

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

        cursor.execute(
            """
            SELECT COALESCE(u.full_name, 'Guest'),
                   sh.origin_id, o.location_name,
                   sh.destination_id, d.location_name,
                   sh.search_date
              FROM search_history sh
              JOIN locations o ON o.location_id = sh.origin_id
              JOIN locations d ON d.location_id = sh.destination_id
              LEFT JOIN users u ON u.user_id = sh.user_id
             ORDER BY sh.search_date DESC, sh.search_id DESC
             LIMIT 5
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

        cursor.execute(
            "SELECT COUNT(*) FROM admin_activity_logs WHERE created_at >= %s",
            [week_start],
        )
        stats['activity_this_week'] = cursor.fetchone()[0] or 0

    return stats


@login_required(login_url='login')
def home(request):
    stats = None
    error = None
    try:
        stats = _sakayguide_stats()
    except (OperationalError, DatabaseError) as exc:
        error = (
            'Could not connect to the SakayGuide database '
            '(sakayguide_db). Start MySQL/XAMPP and try again. '
            f'({exc.__class__.__name__})'
        )
    return render(request, 'home.html', {'stats': stats, 'db_error': error})


@require_http_methods(['GET', 'POST'])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'GET':
        return render(request, 'auth/register.html')

    form_data = {
        'username': request.POST.get('username', ''),
        'first_name': request.POST.get('first_name', ''),
        'last_name': request.POST.get('last_name', ''),
        'email': request.POST.get('email', ''),
        'password': request.POST.get('password', ''),
        'confirm_password': request.POST.get('confirm_password', ''),
    }

    errors = _validate_registration_data(form_data)
    if errors:
        return render(request, 'auth/register.html', {'errors': errors, 'form_data': form_data})

    user = User.objects.create_user(
        username=form_data['username'].strip(),
        first_name=form_data['first_name'].strip(),
        last_name=form_data['last_name'].strip(),
        email=form_data['email'].strip(),
        password=form_data['password'],
    )
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
    return redirect('dashboard')
