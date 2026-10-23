"""Read-only statistics helpers for the SakayGuide admin dashboard.

Every helper in this module is defensive. The dashboard must still render when
the configured database is unreachable or when individual tables have not been
created yet. Missing data is reported as ``None`` so the template can display an
explicit "unavailable" state instead of inventing numbers.

No helper in this module writes to the database: they only issue ``SELECT`` /
``COUNT`` statements.
"""

from django.db import DatabaseError, connection
from django.db.models import Count

from apps.sakay.models import Advisory, Route, TransportMode
from apps.users.models import LegacyUser


def database_available():
    """Return ``True`` when the configured database answers a trivial query."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return True
    except DatabaseError:
        return False


def _table_exists(table):
    """Return ``True`` when ``table`` exists in the current database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) FROM information_schema.tables '
                'WHERE table_schema = DATABASE() AND table_name = %s',
                [table],
            )
            return cursor.fetchone()[0] > 0
    except DatabaseError:
        return False


def _orm_count(model):
    """Return ``model.objects.count()`` or ``None`` when it cannot be read."""
    try:
        return int(model.objects.count())
    except DatabaseError:
        return None


def _raw_count(table):
    """Return ``SELECT COUNT(*)`` for ``table`` or ``None`` when unavailable."""
    if not _table_exists(table):
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM `%s`' % table)
            return int(cursor.fetchone()[0])
    except DatabaseError:
        return None


def _first_available(*values):
    """Return the first non-``None`` value, or ``None``."""
    for value in values:
        if value is not None:
            return value
    return None


def get_summary_stats():
    """Return the ordered list of summary cards shown on the dashboard.

    Each card is a dict with ``key``, ``label``, ``icon``, ``accent`` and
    ``value``. ``value`` is an ``int`` when the underlying table could be read
    and ``None`` when it is unavailable.
    """
    transport_types = _first_available(
        _orm_count(TransportMode),
        _raw_count('transport_types'),
    )
    routes = _first_available(
        _orm_count(Route),
        _raw_count('routes'),
    )
    users = _first_available(
        _orm_count(LegacyUser),
        _raw_count('auth_user'),
    )

    return [
        {
            'key': 'barangays',
            'label': 'Barangays',
            'icon': 'fa-solid fa-map-location-dot',
            'accent': 'primary',
            'value': _raw_count('barangays'),
        },
        {
            'key': 'transport_types',
            'label': 'Transport Types',
            'icon': 'fa-solid fa-bus',
            'accent': 'info',
            'value': transport_types,
        },
        {
            'key': 'vehicles',
            'label': 'Vehicles',
            'icon': 'fa-solid fa-truck',
            'accent': 'warning',
            'value': _raw_count('vehicles'),
        },
        {
            'key': 'routes',
            'label': 'Routes',
            'icon': 'fa-solid fa-route',
            'accent': 'success',
            'value': routes,
        },
        {
            'key': 'users',
            'label': 'Registered Users',
            'icon': 'fa-solid fa-users',
            'accent': 'purple',
            'value': users,
        },
    ]


def get_recent_activity(limit=6):
    """Return recent activity records, or ``None`` when none can be read.

    The primary source is the SakayGuide ``sakay_advisory`` table. When it is
    not present the documented ``feedback`` table is used as a fallback.
    """
    try:
        advisories = list(
            Advisory.objects.select_related('terminal')
            .order_by('-created_at')[:limit]
        )
    except DatabaseError:
        advisories = None

    if advisories is not None:
        return [
            {
                'title': advisory.title,
                'detail': advisory.terminal.name if advisory.terminal else 'Network-wide',
                'category': advisory.category,
                'severity': advisory.severity,
                'status': advisory.status,
                'created_at': advisory.created_at,
            }
            for advisory in advisories
        ]

    if _table_exists('feedback'):
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT id, subject, type, status, created_at '
                    'FROM feedback ORDER BY created_at DESC LIMIT %s',
                    [limit],
                )
                return [
                    {
                        'title': row[1],
                        'detail': row[2],
                        'category': row[2],
                        'severity': 'info',
                        'status': row[3],
                        'created_at': row[4],
                    }
                    for row in cursor.fetchall()
                ]
        except DatabaseError:
            return None

    return None


def get_mode_breakdown():
    """Return ``{'labels': [...], 'values': [...]}`` of routes per transport mode.

    ``None`` is returned when no transport-mode breakdown can be read.
    """
    try:
        rows = list(
            Route.objects.values('transport_mode__name')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
    except DatabaseError:
        rows = None

    if rows:
        breakdown = [
            {'name': row['transport_mode__name'] or 'Unknown', 'total': int(row['total'])}
            for row in rows
        ]
        return {
            'labels': [row['name'] for row in breakdown],
            'values': [row['total'] for row in breakdown],
            'rows': breakdown,
        }

    if _table_exists('routes') and _table_exists('transport_types'):
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT t.name, COUNT(r.id) AS total '
                    'FROM routes r JOIN transport_types t '
                    'ON t.id = r.transport_type_id '
                    'GROUP BY t.name ORDER BY total DESC'
                )
                data = cursor.fetchall()
                if data:
                    breakdown = [
                        {'name': row[0], 'total': int(row[1])} for row in data
                    ]
                    return {
                        'labels': [row['name'] for row in breakdown],
                        'values': [row['total'] for row in breakdown],
                        'rows': breakdown,
                    }
        except DatabaseError:
            return None

    return None


def get_barangay_overview(limit=8):
    """Return raw barangay rows when a ``barangays`` table exists, else ``None``."""
    if not _table_exists('barangays'):
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM barangays LIMIT %s', [limit])
            columns = [column[0] for column in cursor.description]
            return {
                'columns': columns,
                'rows': [list(row) for row in cursor.fetchall()],
            }
    except DatabaseError:
        return None
