"""Views for the SakayGuide administrator dashboard.

Everything in this module is protected by :func:`administrator_required`.
The dashboard talks to both databases:

* Django's default database owns accounts, sessions and personal info.
* ``sakayguide_db`` owns locations, routes, stops, fares, transfers, search
  history and administrator audit entries.

Records are normally deactivated instead of hard-deleted when other tables
still reference them, which mirrors the foreign-key rules in the SQL schema.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Avg, Count, Max, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from routes.models import (
    AdminActivityLog,
    FareType,
    Location,
    Route,
    RouteFare,
    RouteLandmark,
    RouteStop,
    RouteTransfer,
    SavedRoute,
    SearchHistory,
    TransportationType,
)
from routes.network_repair import ensure_route_stops

from .admin_forms import (
    AdminUserCreateForm,
    AdminUserEditForm,
    FareTypeForm,
    LocationForm,
    RouteFareForm,
    RouteForm,
    RouteStopForm,
    RouteTransferForm,
    TransportationTypeForm,
    role_for,
)
from .audit import log_activity, sakay_user_for
from .permissions import administrator_required

User = get_user_model()

PAGE_SIZE = 15
TRANSIT_PAGE_SIZE = 20

# The two local transport modes SakayGuide manages: Jeepney covers the
# fixed routes and Tricycle covers the short service areas around the
# barangays. Other records that already exist in the database stay visible
# and editable, but these are the ones the management screens put first.
SUPPORTED_TRANSPORT_MODES = ['Jeepney', 'Tricycle']


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _google_maps_config():
    """Browser configuration for Google Maps (key is never hard-coded)."""
    api_key = (getattr(settings, 'GOOGLE_MAPS_API_KEY', '') or '').strip()
    return {
        'api_key': api_key,
        'enabled': bool(api_key),
        'language': getattr(settings, 'GOOGLE_MAPS_LANGUAGE', 'en'),
        'region': getattr(settings, 'GOOGLE_MAPS_REGION', 'PH'),
        'center': {'lat': 9.9926, 'lng': 122.8135},
        'bounds': {
            'south': 9.70,
            'west': 122.66,
            'north': 10.12,
            'east': 122.99,
        },
    }


def _paginate(request, queryset, per_page=PAGE_SIZE, page_param='page'):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get(page_param))


def _log_admin_action(request, action_type, table, record_id=None, description=''):
    return log_activity(
        request.user,
        action_type,
        table,
        record_id=record_id,
        description=description,
    )


def _sync_user_mirror(user, role=None):
    """Keep the SakayGuide ``users`` mirror in step with Django auth."""
    if role is None:
        role = 'admin' if user.is_staff else 'commuter'
    status = 'active' if user.is_active else 'inactive'
    try:
        return sakay_user_for(user, role=role, status=status)
    except DatabaseError:
        # The audit helper already logs connection problems; the management
        # action itself must still succeed when sakayguide_db is offline.
        return None


def _ensure_route_endpoints(route):
    """Give a new route its minimum boarding and drop-off stops.

    A route is only usable by the commuter search when it has ordered stops.
    Administrators often create the route first and add intermediate stops
    afterwards, so the origin and destination are recorded automatically -
    including on an edit of a route whose stop list is missing one of them.

    While the route still holds exactly the auto-created pair (order 1 and 2,
    both flagged as transfer points), the destination stop is re-synced to
    the route's recorded ``estimated_travel_time`` on every save. That keeps
    the commuter side showing the updated travel time straight away, without
    the administrator having to re-enter it in the stop list. As soon as the
    administrator adds a third stop or clears the transfer flag, the pair is
    treated as hand-managed and left untouched.
    """
    created = ensure_route_stops(route)
    stops = list(route.stops.order_by('stop_order'))
    if (
        len(stops) == 2
        and stops[0].stop_order == 1
        and stops[1].stop_order == 2
        and stops[0].is_transfer_point
        and stops[1].is_transfer_point
        and stops[0].estimated_stop_time == 0
        and stops[1].estimated_stop_time != route.estimated_travel_time
    ):
        stops[1].estimated_stop_time = route.estimated_travel_time
        stops[1].save(update_fields=['estimated_stop_time'])
    return len(created)


def _friendly_database_error(exc):
    text = str(exc)
    if 'Invalid transfer' in text:
        return (
            'That transfer is invalid: the transfer location must be a stop '
            'on both routes.'
        )
    if 'foreign key' in text.lower():
        return (
            'That record is still used by other SakayGuide data. '
            'Deactivate it instead of deleting it.'
        )
    if 'Duplicate entry' in text:
        return 'A record with those details already exists.'
    return 'The database rejected that change. Check the values and try again.'


def _coords(location):
    if location is None:
        return None
    if location.latitude is None or location.longitude is None:
        return None
    return {
        'lat': float(location.latitude),
        'lng': float(location.longitude),
    }


def _location_marker(location):
    return {
        'id': location.pk,
        'name': location.location_name,
        'type': location.location_type,
        'barangay': location.barangay.barangay_name,
        'status': location.status,
        'has_coords': _coords(location) is not None,
        'coords': _coords(location),
        'edit_url': reverse('management_location_edit', args=[location.pk]),
    }


def _route_map_payload(route):
    """Build the JSON object consumed by the route management map."""
    if route is None:
        return None

    stops = list(
        route.stops.select_related('location').order_by('stop_order')
    )
    markers = []
    ordered_points = []

    origin_point = _coords(route.origin)
    destination_point = _coords(route.destination)
    if origin_point:
        ordered_points.append(origin_point)
        markers.append({
            'name': route.origin.location_name,
            'role': 'origin',
            'coords': origin_point,
        })
    if destination_point:
        markers.append({
            'name': route.destination.location_name,
            'role': 'destination',
            'coords': destination_point,
        })

    for stop in stops:
        point = _coords(stop.location)
        if not point:
            continue
        markers.append({
            'name': stop.location.location_name,
            'role': 'transfer' if stop.is_transfer_point else 'stop',
            'order': stop.stop_order,
            'coords': point,
        })
        if point != origin_point and point != destination_point:
            ordered_points.append(point)

    if destination_point:
        ordered_points.append(destination_point)

    return {
        'id': route.pk,
        'code': route.route_code,
        'name': route.route_name,
        'origin': route.origin.location_name,
        'destination': route.destination.location_name,
        'markers': markers,
        'points': ordered_points,
        'path_ready': bool(origin_point and destination_point),
        'missing_coords': [
            stop.location.location_name for stop in stops
            if _coords(stop.location) is None
        ],
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def _dashboard_stats():
    """Collect account and transit statistics for the overview page."""
    today = timezone.localdate()
    week_start = today - timedelta(days=6)
    previous_week_start = week_start - timedelta(days=7)

    stats = {
        'total_users': User.objects.count(),
        'total_commuters': User.objects.filter(is_staff=False).count(),
        'total_admins': User.objects.filter(is_staff=True).count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'inactive_users': User.objects.filter(is_active=False).count(),
        'new_users_week': User.objects.filter(
            date_joined__date__gte=week_start,
        ).count(),
    }

    try:
        stats.update({
            'total_locations': Location.objects.count(),
            'active_locations': Location.objects.filter(status='active').count(),
            'inactive_locations': Location.objects.filter(status='inactive').count(),
            'locations_with_coords': Location.objects.filter(
                latitude__isnull=False, longitude__isnull=False,
            ).count(),
            'locations_missing_coords': Location.objects.filter(
                Q(latitude__isnull=True) | Q(longitude__isnull=True)
            ).count(),
            'total_routes': Route.objects.count(),
            'active_routes': Route.objects.filter(status='active').count(),
            'inactive_routes': Route.objects.filter(status='inactive').count(),
            'total_stops': RouteStop.objects.count(),
            'total_transfers': RouteTransfer.objects.count(),
            'active_fares': RouteFare.objects.filter(status='active').count(),
            'total_fares': RouteFare.objects.count(),
            'transport_modes': TransportationType.objects.filter(
                status='active'
            ).count(),
            'fare_categories': FareType.objects.filter(status='active').count(),
            'barangays': Location.objects.values('barangay_id').distinct().count(),
            'total_searches': SearchHistory.objects.count(),
            'searches_week': SearchHistory.objects.filter(
                search_date__date__gte=week_start,
            ).count(),
            'searches_previous_week': SearchHistory.objects.filter(
                search_date__date__gte=previous_week_start,
                search_date__date__lt=week_start,
            ).count(),
            'activity_week': AdminActivityLog.objects.filter(
                created_at__date__gte=week_start,
            ).count(),
            'routes_without_stops': Route.objects.annotate(
                stop_count=Count('stops')
            ).filter(stop_count=0).count(),
            'routes_without_fares': Route.objects.annotate(
                fare_count=Count('fares', filter=Q(fares__status='active'))
            ).filter(fare_count=0).count(),
            'recent_locations': list(
                Location.objects.select_related('barangay')
                .order_by('-location_id')[:6]
            ),
            'recent_routes': list(
                Route.objects.select_related(
                    'origin', 'destination', 'transport_type'
                ).order_by('-route_id')[:5]
            ),
            'missing_locations': list(
                Location.objects.select_related('barangay')
                .filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
                .order_by('location_name')[:6]
            ),
            'recent_logs': list(
                AdminActivityLog.objects.select_related('admin')
                .order_by('-created_at', '-log_id')[:8]
            ),
            'recent_searches': list(
                SearchHistory.objects.select_related(
                    'origin', 'destination', 'user'
                ).order_by('-search_date', '-search_id')[:8]
            ),
            'transport_breakdown': list(
                TransportationType.objects.annotate(
                    route_count=Count(
                        'routes', filter=Q(routes__status='active')
                    )
                ).order_by('-route_count', 'transport_name')
            ),
            'location_type_breakdown': list(
                Location.objects.values('location_type')
                .annotate(count=Count('location_id'))
                .order_by('-count', 'location_type')[:8]
            ),
            'top_destinations': list(
                SearchHistory.objects.values('destination__location_name')
                .annotate(count=Count('search_id'))
                .order_by('-count')[:5]
            ),
        })

        daily_rows = (
            SearchHistory.objects.filter(search_date__date__gte=week_start)
            .values('search_date__date')
            .annotate(count=Count('search_id'))
        )
        daily = {
            row['search_date__date']: row['count'] for row in daily_rows
        }
        activity = []
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            activity.append({
                'date': day.isoformat(),
                'label': day.strftime('%a'),
                'full_label': day.strftime('%b %d'),
                'count': daily.get(day, 0),
            })
        stats['search_activity'] = activity
        stats['search_peak'] = max(
            activity, key=lambda item: item['count']
        ) if activity else None

        total_routes = stats['total_routes'] or 0
        mapped = stats['locations_with_coords'] or 0
        total_locations = stats['total_locations'] or 0
        stats['coverage_percent'] = (
            round(mapped * 100 / total_locations) if total_locations else 0
        )
        checks = [
            {
                'label': 'Locations with coordinates',
                'percent': stats['coverage_percent'],
                'detail': f'{mapped} of {total_locations} locations',
                'icon': 'fa-map-pin',
            },
            {
                'label': 'Routes with stops',
                'percent': (
                    round((total_routes - stats['routes_without_stops'])
                          * 100 / total_routes)
                    if total_routes else 0
                ),
                'detail': (
                    f"{total_routes - stats['routes_without_stops']} of "
                    f'{total_routes} routes'
                ),
                'icon': 'fa-circle-stop',
            },
            {
                'label': 'Routes with active fares',
                'percent': (
                    round((total_routes - stats['routes_without_fares'])
                          * 100 / total_routes)
                    if total_routes else 0
                ),
                'detail': (
                    f"{total_routes - stats['routes_without_fares']} of "
                    f'{total_routes} routes'
                ),
                'icon': 'fa-ticket',
            },
        ]
        stats['health_checks'] = checks
        stats['network_health'] = (
            round(sum(check['percent'] for check in checks) / len(checks))
            if checks else 0
        )
        stats['sakayguide_connected'] = True
    except DatabaseError as exc:
        stats['sakayguide_connected'] = False
        stats['db_error'] = (
            'The SakayGuide transit database is unavailable. Account '
            'statistics are still shown, but locations, routes and audit '
            f'data could not be loaded. ({exc.__class__.__name__})'
        )
        for key, value in {
            'total_locations': 0, 'active_locations': 0,
            'inactive_locations': 0, 'locations_with_coords': 0,
            'locations_missing_coords': 0, 'total_routes': 0,
            'active_routes': 0, 'inactive_routes': 0, 'total_stops': 0,
            'total_transfers': 0, 'active_fares': 0, 'total_fares': 0,
            'transport_modes': 0, 'fare_categories': 0, 'barangays': 0,
            'total_searches': 0, 'searches_week': 0,
            'searches_previous_week': 0, 'activity_week': 0,
            'routes_without_stops': 0, 'routes_without_fares': 0,
            'coverage_percent': 0, 'network_health': 0,
        }.items():
            stats.setdefault(key, value)
        stats['recent_locations'] = []
        stats['recent_routes'] = []
        stats['missing_locations'] = []
        stats['recent_logs'] = []
        stats['recent_searches'] = []
        stats['transport_breakdown'] = []
        stats['location_type_breakdown'] = []
        stats['top_destinations'] = []
        stats['search_activity'] = []
        stats['search_peak'] = None
        stats['health_checks'] = []
    return stats


@administrator_required
def dashboard(request):
    stats = _dashboard_stats()
    return render(request, 'management/dashboard.html', {
        'stats': stats,
        'generated_at': timezone.now(),
    })


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

@administrator_required
def location_list(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    missing = request.GET.get('missing', '')
    location_type = request.GET.get('type', '')

    locations = Location.objects.select_related('barangay').annotate(
        stop_count=Count('stops', distinct=True),
        transfer_count=Count('transfers', distinct=True),
    )

    if query:
        locations = locations.filter(
            Q(location_name__icontains=query)
            | Q(address__icontains=query)
            | Q(barangay__barangay_name__icontains=query)
            | Q(location_type__icontains=query)
        )
    if status in ('active', 'inactive'):
        locations = locations.filter(status=status)
    if missing == '1':
        locations = locations.filter(
            Q(latitude__isnull=True) | Q(longitude__isnull=True)
        )
    elif missing == '0':
        locations = locations.filter(
            latitude__isnull=False, longitude__isnull=False,
        )
    if location_type:
        locations = locations.filter(location_type=location_type)

    locations = locations.order_by('location_name')
    types = list(
        Location.objects.values_list(
            'location_type', flat=True
        ).distinct().order_by('location_type')
    )
    page = _paginate(request, locations)
    return render(request, 'management/locations.html', {
        'locations': page,
        'query': query,
        'status': status,
        'missing': missing,
        'location_type': location_type,
        'location_types': types,
        'total_count': Location.objects.count(),
        'active_count': Location.objects.filter(status='active').count(),
        'missing_count': Location.objects.filter(
            Q(latitude__isnull=True) | Q(longitude__isnull=True)
        ).count(),
    })


def _location_form_initial(request):
    initial = {}
    try:
        if request.GET.get('lat') and request.GET.get('lng'):
            initial['latitude'] = float(request.GET['lat'])
            initial['longitude'] = float(request.GET['lng'])
    except (TypeError, ValueError):
        pass
    return initial


@administrator_required
def location_create(request):
    form = LocationForm(
        request.POST or None,
        initial=_location_form_initial(request),
    )
    if request.method == 'POST' and form.is_valid():
        location = form.save()
        _log_admin_action(
            request, 'CREATE', 'locations', location.pk,
            f'Created location "{location.location_name}" '
            f'({location.location_type}) in {location.barangay}.',
        )
        messages.success(
            request, f'Location "{location.location_name}" was created.'
        )
        return redirect('management_locations')

    return render(request, 'management/location_form.html', {
        'form': form,
        'mode': 'create',
        'google_maps': _google_maps_config(),
        'location_type_suggestions': [
            'terminal', 'stop', 'landmark', 'establishment', 'government',
            'hospital', 'school', 'market', 'barangay', 'other',
        ],
    })


@administrator_required
def location_edit(request, pk):
    location = get_object_or_404(Location, pk=pk)
    form = LocationForm(request.POST or None, instance=location)
    if request.method == 'POST' and form.is_valid():
        location = form.save()
        _log_admin_action(
            request, 'UPDATE', 'locations', location.pk,
            f'Updated location "{location.location_name}" '
            f'({location.location_type}).',
        )
        messages.success(
            request, f'Location "{location.location_name}" was updated.'
        )
        return redirect('management_locations')

    return render(request, 'management/location_form.html', {
        'form': form,
        'location': location,
        'mode': 'edit',
        'google_maps': _google_maps_config(),
        'location_type_suggestions': [
            'terminal', 'stop', 'landmark', 'establishment', 'government',
            'hospital', 'school', 'market', 'barangay', 'other',
        ],
    })


@administrator_required
@require_POST
def location_delete(request, pk):
    location = get_object_or_404(Location, pk=pk)
    name = location.location_name

    references = []
    try:
        if Route.objects.filter(
            Q(origin=location) | Q(destination=location)
        ).exists():
            references.append('routes')
        if RouteStop.objects.filter(location=location).exists():
            references.append('route stops')
        if RouteTransfer.objects.filter(transfer_location=location).exists():
            references.append('transfer connections')
        if RouteLandmark.objects.filter(location=location).exists():
            references.append('landmarks')
        if SavedRoute.objects.filter(
            Q(origin=location) | Q(destination=location)
        ).exists():
            references.append('saved routes')
        if SearchHistory.objects.filter(
            Q(origin=location) | Q(destination=location)
        ).exists():
            references.append('search history')
    except DatabaseError:
        references.append('related transit records')

    try:
        if references:
            location.status = 'inactive'
            location.save(update_fields=['status'])
            _log_admin_action(
                request, 'DEACTIVATE', 'locations', location.pk,
                f'Deactivated location "{name}" because it is referenced by '
                f'{", ".join(references)}.',
            )
            messages.warning(
                request,
                f'"{name}" is still used by {", ".join(references)}, so it was '
                'deactivated instead of deleted. Existing records remain intact.',
            )
        else:
            location.delete()
            _log_admin_action(
                request, 'DELETE', 'locations', pk,
                f'Deleted unused location "{name}".',
            )
            messages.success(request, f'Location "{name}" was deleted.')
    except (IntegrityError, DatabaseError) as exc:
        messages.error(request, _friendly_database_error(exc))

    return redirect('management_locations')


@administrator_required
@require_POST
def location_toggle(request, pk):
    location = get_object_or_404(Location, pk=pk)
    location.status = (
        'inactive' if location.status == 'active' else 'active'
    )
    location.save(update_fields=['status'])
    _log_admin_action(
        request,
        'ACTIVATE' if location.status == 'active' else 'DEACTIVATE',
        'locations',
        location.pk,
        f'{"Activated" if location.status == "active" else "Deactivated"} '
        f'location "{location.location_name}".',
    )
    messages.success(
        request,
        f'Location "{location.location_name}" is now {location.status}.',
    )
    return redirect('management_locations')


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@administrator_required
def route_list(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    transport_type = request.GET.get('transport', '')
    mode = request.GET.get('mode', '').strip()

    routes = Route.objects.select_related(
        'origin', 'destination', 'transport_type'
    ).annotate(
        stop_count=Count('stops', distinct=True),
        min_fare=Min(
            'fares__total_estimated_fare', filter=Q(fares__status='active')
        ),
    )

    if query:
        routes = routes.filter(
            Q(route_code__icontains=query)
            | Q(route_name__icontains=query)
            | Q(origin__location_name__icontains=query)
            | Q(destination__location_name__icontains=query)
        )
    if status in ('active', 'inactive'):
        routes = routes.filter(status=status)
    if transport_type:
        routes = routes.filter(transport_type_id=transport_type)
    if mode:
        routes = routes.filter(transport_type__transport_name__iexact=mode)

    routes = routes.order_by('route_code')
    page = _paginate(request, routes)
    return render(request, 'management/routes.html', {
        'routes': page,
        'query': query,
        'status': status,
        'transport_type': transport_type,
        'mode': mode,
        'transport_types': TransportationType.objects.order_by('transport_name'),
        'supported_modes': SUPPORTED_TRANSPORT_MODES,
        'jeepney_count': Route.objects.filter(
            status='active',
            transport_type__transport_name__iexact='Jeepney',
        ).count(),
        'tricycle_count': Route.objects.filter(
            status='active',
            transport_type__transport_name__iexact='Tricycle',
        ).count(),
        'bus_count': Route.objects.filter(
            status='active',
            transport_type__transport_name__iexact='Bus',
        ).count(),
        'total_count': Route.objects.count(),
        'active_count': Route.objects.filter(status='active').count(),
        'inactive_count': Route.objects.filter(status='inactive').count(),
        'total_stops': RouteStop.objects.count(),
    })


@administrator_required
def route_create(request):
    form = RouteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        route = form.save()
        endpoint_count = _ensure_route_endpoints(route)
        _log_admin_action(
            request, 'CREATE', 'routes', route.pk,
            f'Created route "{route.route_code}" ({route.route_name}) '
            f'from {route.origin} to {route.destination}.',
        )
        messages.success(
            request,
            f'Route "{route.route_code}" was created. '
            + (
                'Its boarding and drop-off stops were added automatically, '
                'so commuters can already find it in Find My Route. '
                if endpoint_count else ''
            )
            + 'You can now add more stops, fares and transfer connections.',
        )
        return redirect('management_route_detail', pk=route.pk)

    return render(request, 'management/route_form.html', {
        'form': form,
        'mode': 'create',
    })


@administrator_required
def route_edit(request, pk):
    route = get_object_or_404(Route, pk=pk)
    form = RouteForm(request.POST or None, instance=route)
    if request.method == 'POST' and form.is_valid():
        route = form.save()
        endpoint_count = _ensure_route_endpoints(route)
        _log_admin_action(
            request, 'UPDATE', 'routes', route.pk,
            f'Updated route "{route.route_code}" ({route.route_name}).',
        )
        messages.success(
            request,
            f'Route "{route.route_code}" was updated.'
            + (
                ' Its boarding and drop-off stops were added automatically.'
                if endpoint_count else ''
            ),
        )
        return redirect('management_route_detail', pk=route.pk)

    return render(request, 'management/route_form.html', {
        'form': form,
        'route': route,
        'mode': 'edit',
    })


@administrator_required
def route_detail(request, pk):
    route = get_object_or_404(
        Route.objects.select_related(
            'origin', 'destination', 'transport_type'
        ),
        pk=pk,
    )
    stops = list(
        route.stops.select_related(
            'location', 'location__barangay'
        ).order_by('stop_order')
    )
    fares = list(
        route.fares.select_related('fare_type').order_by(
            '-effective_date', '-fare_id'
        )
    )
    transfers_from = list(
        route.transfers_from.select_related(
            'to_route', 'transfer_location'
        ).order_by('transfer_id')
    )
    transfers_to = list(
        route.transfers_to.select_related(
            'from_route', 'transfer_location'
        ).order_by('transfer_id')
    )
    active_fares = [fare for fare in fares if fare.status == 'active']

    return render(request, 'management/route_detail.html', {
        'route': route,
        'stops': stops,
        'fares': fares,
        'active_fares': active_fares,
        'transfers_from': transfers_from,
        'transfers_to': transfers_to,
        'route_map_data': _route_map_payload(route),
        'google_maps': _google_maps_config(),
    })


@administrator_required
@require_POST
def route_delete(request, pk):
    route = get_object_or_404(Route, pk=pk)
    label = f'{route.route_code} - {route.route_name}'
    references = []
    if route.stops.exists():
        references.append('stops')
    if route.fares.exists():
        references.append('fare records')
    if route.transfers_from.exists() or route.transfers_to.exists():
        references.append('transfer connections')
    if route.landmarks.exists():
        references.append('route landmarks')

    try:
        if references:
            route.status = 'inactive'
            route.save(update_fields=['status'])
            _log_admin_action(
                request, 'DEACTIVATE', 'routes', route.pk,
                f'Deactivated route "{label}" because it has '
                f'{", ".join(references)}.',
            )
            messages.warning(
                request,
                f'"{label}" has {", ".join(references)}, so it was deactivated '
                'instead of deleted. This preserves fare and transfer history.',
            )
        else:
            route.delete()
            _log_admin_action(
                request, 'DELETE', 'routes', pk,
                f'Deleted unused route "{label}".',
            )
            messages.success(request, f'Route "{label}" was deleted.')
    except (IntegrityError, DatabaseError) as exc:
        messages.error(request, _friendly_database_error(exc))

    return redirect('management_routes')


@administrator_required
@require_POST
def route_toggle(request, pk):
    route = get_object_or_404(Route, pk=pk)
    route.status = 'inactive' if route.status == 'active' else 'active'
    route.save(update_fields=['status'])
    _log_admin_action(
        request,
        'ACTIVATE' if route.status == 'active' else 'DEACTIVATE',
        'routes',
        route.pk,
        f'{"Activated" if route.status == "active" else "Deactivated"} '
        f'route "{route.route_code}".',
    )
    messages.success(
        request, f'Route "{route.route_code}" is now {route.status}.'
    )
    return redirect('management_route_detail', pk=route.pk)


# ---------------------------------------------------------------------------
# Stops
# ---------------------------------------------------------------------------

@administrator_required
def stop_list(request):
    query = request.GET.get('q', '').strip()
    route_id = request.GET.get('route', '')

    stops = RouteStop.objects.select_related(
        'route', 'location', 'location__barangay'
    )
    if query:
        stops = stops.filter(
            Q(location__location_name__icontains=query)
            | Q(route__route_code__icontains=query)
            | Q(route__route_name__icontains=query)
        )
    if route_id:
        stops = stops.filter(route_id=route_id)
    stops = stops.order_by('route__route_code', 'stop_order')
    page = _paginate(request, stops, TRANSIT_PAGE_SIZE)

    return render(request, 'management/stops.html', {
        'stops': page,
        'query': query,
        'route_id': route_id,
        'routes': Route.objects.order_by('route_code'),
        'total_count': RouteStop.objects.count(),
    })


@administrator_required
def stop_create(request):
    route = None
    route_id = request.GET.get('route') or request.POST.get('route_context')
    if route_id:
        route = get_object_or_404(Route, pk=route_id)

    form = RouteStopForm(request.POST or None, route=route)
    if request.method == 'POST' and form.is_valid():
        stop = form.save()
        _log_admin_action(
            request, 'CREATE', 'route_stops', stop.pk,
            f'Added stop "{stop.location}" at position {stop.stop_order} '
            f'to route "{stop.route.route_code}".',
        )
        messages.success(
            request,
            f'Stop "{stop.location}" was added to {stop.route.route_code}.',
        )
        if route:
            return redirect('management_route_detail', pk=route.pk)
        return redirect('management_stops')

    return render(request, 'management/transit_form.html', {
        'form': form,
        'route': route,
        'title': 'Add a route stop',
        'subtitle': (
            f'Add a boarding point, landmark or drop-off point to '
            f'{route.route_code}.' if route else
            'Add a stop to a route in the transit network.'
        ),
        'submit_label': 'Save stop',
        'cancel_url': (
            reverse('management_route_detail', args=[route.pk])
            if route else reverse('management_stops')
        ),
    })


@administrator_required
def stop_edit(request, pk):
    stop = get_object_or_404(
        RouteStop.objects.select_related('route', 'location'), pk=pk
    )
    form = RouteStopForm(request.POST or None, instance=stop, route=stop.route)
    if request.method == 'POST' and form.is_valid():
        stop = form.save()
        _log_admin_action(
            request, 'UPDATE', 'route_stops', stop.pk,
            f'Updated stop "{stop.location}" on route '
            f'"{stop.route.route_code}".',
        )
        messages.success(request, 'Route stop was updated.')
        return redirect('management_route_detail', pk=stop.route_id)

    return render(request, 'management/transit_form.html', {
        'form': form,
        'route': stop.route,
        'stop': stop,
        'title': 'Edit route stop',
        'subtitle': f'{stop.location} on {stop.route.route_code}.',
        'submit_label': 'Save stop',
        'cancel_url': reverse('management_route_detail', args=[stop.route_id]),
    })


@administrator_required
@require_POST
def stop_delete(request, pk):
    stop = get_object_or_404(
        RouteStop.objects.select_related('route', 'location'), pk=pk
    )
    route_id = stop.route_id
    stop_label = f'{stop.location} on {stop.route.route_code}'
    if RouteTransfer.objects.filter(
        Q(from_route=stop.route) | Q(to_route=stop.route),
        transfer_location=stop.location,
    ).exists():
        messages.error(
            request,
            f'"{stop_label}" is used by a transfer connection. Remove the '
            'transfer first.',
        )
        return redirect('management_route_detail', pk=route_id)

    try:
        stop.delete()
        _log_admin_action(
            request, 'DELETE', 'route_stops', pk,
            f'Removed stop "{stop_label}".',
        )
        messages.success(request, f'Stop "{stop_label}" was removed.')
    except (IntegrityError, DatabaseError) as exc:
        messages.error(request, _friendly_database_error(exc))
    return redirect('management_route_detail', pk=route_id)


# ---------------------------------------------------------------------------
# Fares
# ---------------------------------------------------------------------------

def _retire_older_active_fares(fare):
    """Keep one authoritative active row per route and fare category.

    The newest saved amount must be the one every commuter page reads. Any
    older still-active row for the same route/category is moved to the
    recorded history instead of being deleted, so the administrator's change
    can never be shadowed by a duplicate record.
    """
    if fare.status != RouteFare.STATUS_ACTIVE:
        return
    siblings = RouteFare.objects.filter(
        route_id=fare.route_id,
        fare_type_id=fare.fare_type_id,
        status=RouteFare.STATUS_ACTIVE,
        effective_date__lte=fare.effective_date,
    ).exclude(pk=fare.pk)
    for sibling in siblings:
        sibling.status = RouteFare.STATUS_EXPIRED
        candidate = fare.effective_date - timedelta(days=1)
        if sibling.effective_date and candidate >= sibling.effective_date:
            sibling.expiry_date = candidate
        sibling.save(update_fields=['status', 'expiry_date'])


@administrator_required
def fare_list(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    route_id = request.GET.get('route', '')

    fares = RouteFare.objects.select_related('route', 'fare_type')
    if query:
        fares = fares.filter(
            Q(route__route_code__icontains=query)
            | Q(route__route_name__icontains=query)
            | Q(fare_type__fare_type_name__icontains=query)
        )
    if status:
        fares = fares.filter(status=status)
    if route_id:
        fares = fares.filter(route_id=route_id)
    fares = fares.order_by('-effective_date', '-fare_id')
    page = _paginate(request, fares, TRANSIT_PAGE_SIZE)

    return render(request, 'management/fares.html', {
        'fares': page,
        'query': query,
        'status': status,
        'route_id': route_id,
        'routes': Route.objects.order_by('route_code'),
        'status_choices': RouteFare.FARE_STATUS_CHOICES,
        'total_count': RouteFare.objects.count(),
        'active_count': RouteFare.objects.filter(status='active').count(),
    })


@administrator_required
def fare_create(request):
    route = None
    route_id = request.GET.get('route') or request.POST.get('route_context')
    if route_id:
        route = get_object_or_404(Route, pk=route_id)

    form = RouteFareForm(request.POST or None, route=route)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic(using='sakayguide'):
                fare = form.save()
                _retire_older_active_fares(fare)
        except (IntegrityError, DatabaseError) as exc:
            messages.error(request, _friendly_database_error(exc))
        else:
            _log_admin_action(
                request, 'CREATE', 'route_fares', fare.pk,
                f'Added {fare.fare_type} fare of PHP {fare.total_estimated_fare} '
                f'to route "{fare.route.route_code}".',
            )
            messages.success(
                request,
                f'{fare.fare_type} fare saved at '
                f'PHP {fare.total_estimated_fare} for route '
                f'{fare.route.route_code}. Commuter pages now use this amount.',
            )
            if route:
                return redirect('management_route_detail', pk=route.pk)
            return redirect('management_fares')

    return render(request, 'management/transit_form.html', {
        'form': form,
        'route': route,
        'title': 'Add a fare record',
        'subtitle': (
            f'Record a fare for {route.route_code}.' if route else
            'Record a fare for a route.'
        ),
        'submit_label': 'Save fare',
        'cancel_url': (
            reverse('management_route_detail', args=[route.pk])
            if route else reverse('management_fares')
        ),
    })


@administrator_required
def fare_edit(request, pk):
    fare = get_object_or_404(
        RouteFare.objects.select_related('route', 'fare_type'), pk=pk
    )
    form = RouteFareForm(
        request.POST or None, instance=fare, route=fare.route
    )
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic(using='sakayguide'):
                fare = form.save()
                _retire_older_active_fares(fare)
        except (IntegrityError, DatabaseError) as exc:
            messages.error(request, _friendly_database_error(exc))
        else:
            _log_admin_action(
                request, 'UPDATE', 'route_fares', fare.pk,
                f'Updated {fare.fare_type} fare on route '
                f'"{fare.route.route_code}" to PHP {fare.total_estimated_fare}.',
            )
            messages.success(
                request,
                f'{fare.fare_type} fare updated to '
                f'PHP {fare.total_estimated_fare} for route '
                f'{fare.route.route_code}. Commuter pages now use this amount.',
            )
            return redirect('management_route_detail', pk=fare.route_id)

    return render(request, 'management/transit_form.html', {
        'form': form,
        'route': fare.route,
        'title': 'Edit fare record',
        'subtitle': f'{fare.fare_type} on {fare.route.route_code}.',
        'submit_label': 'Save fare',
        'cancel_url': reverse(
            'management_route_detail', args=[fare.route_id]
        ),
    })


@administrator_required
@require_POST
def fare_delete(request, pk):
    fare = get_object_or_404(
        RouteFare.objects.select_related('route', 'fare_type'), pk=pk
    )
    route_id = fare.route_id
    try:
        fare.delete()
        _log_admin_action(
            request, 'DELETE', 'route_fares', pk,
            f'Deleted {fare.fare_type} fare from route '
            f'"{fare.route.route_code}".',
        )
        messages.success(request, 'Fare record was deleted.')
    except (IntegrityError, DatabaseError) as exc:
        messages.error(request, _friendly_database_error(exc))
    return redirect('management_route_detail', pk=route_id)


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------

@administrator_required
def transfer_list(request):
    query = request.GET.get('q', '').strip()
    route_id = request.GET.get('route', '')

    transfers = RouteTransfer.objects.select_related(
        'from_route', 'to_route', 'transfer_location'
    )
    if query:
        transfers = transfers.filter(
            Q(from_route__route_code__icontains=query)
            | Q(to_route__route_code__icontains=query)
            | Q(transfer_location__location_name__icontains=query)
            | Q(transfer_instructions__icontains=query)
        )
    if route_id:
        transfers = transfers.filter(
            Q(from_route_id=route_id) | Q(to_route_id=route_id)
        )
    transfers = transfers.order_by('from_route__route_code', 'transfer_id')
    page = _paginate(request, transfers, TRANSIT_PAGE_SIZE)

    return render(request, 'management/transfers.html', {
        'transfers': page,
        'query': query,
        'route_id': route_id,
        'routes': Route.objects.order_by('route_code'),
        'total_count': RouteTransfer.objects.count(),
    })


@administrator_required
def transfer_create(request):
    route = None
    route_id = request.GET.get('route') or request.POST.get('route_context')
    if route_id:
        route = get_object_or_404(Route, pk=route_id)

    form = RouteTransferForm(request.POST or None, route=route)
    if request.method == 'POST' and form.is_valid():
        try:
            transfer = form.save()
        except (IntegrityError, DatabaseError) as exc:
            messages.error(request, _friendly_database_error(exc))
        else:
            _log_admin_action(
                request, 'CREATE', 'route_transfers', transfer.pk,
                f'Added transfer from "{transfer.from_route.route_code}" to '
                f'"{transfer.to_route.route_code}" at '
                f'{transfer.transfer_location}.',
            )
            messages.success(request, 'Transfer connection was created.')
            if route:
                return redirect('management_route_detail', pk=route.pk)
            return redirect('management_transfers')

    return render(request, 'management/transit_form.html', {
        'form': form,
        'route': route,
        'title': 'Add a transfer connection',
        'subtitle': (
            f'Connect {route.route_code} with another route. The transfer '
            'location must already be a stop on both routes.' if route else
            'Connect two routes through a shared stop.'
        ),
        'submit_label': 'Save transfer',
        'cancel_url': (
            reverse('management_route_detail', args=[route.pk])
            if route else reverse('management_transfers')
        ),
    })


@administrator_required
def transfer_edit(request, pk):
    transfer = get_object_or_404(
        RouteTransfer.objects.select_related(
            'from_route', 'to_route', 'transfer_location'
        ),
        pk=pk,
    )
    form = RouteTransferForm(
        request.POST or None, instance=transfer,
        route=transfer.from_route,
    )
    if request.method == 'POST' and form.is_valid():
        try:
            transfer = form.save()
        except (IntegrityError, DatabaseError) as exc:
            messages.error(request, _friendly_database_error(exc))
        else:
            _log_admin_action(
                request, 'UPDATE', 'route_transfers', transfer.pk,
                f'Updated transfer from "{transfer.from_route.route_code}" to '
                f'"{transfer.to_route.route_code}" at '
                f'{transfer.transfer_location}.',
            )
            messages.success(request, 'Transfer connection was updated.')
            return redirect(
                'management_route_detail', pk=transfer.from_route_id
            )

    return render(request, 'management/transit_form.html', {
        'form': form,
        'route': transfer.from_route,
        'title': 'Edit transfer connection',
        'subtitle': (
            f'{transfer.from_route.route_code} to '
            f'{transfer.to_route.route_code} at {transfer.transfer_location}.'
        ),
        'submit_label': 'Save transfer',
        'cancel_url': reverse(
            'management_route_detail', args=[transfer.from_route_id]
        ),
    })


@administrator_required
@require_POST
def transfer_delete(request, pk):
    transfer = get_object_or_404(
        RouteTransfer.objects.select_related('from_route', 'to_route'), pk=pk
    )
    route_id = transfer.from_route_id
    label = (
        f'{transfer.from_route.route_code} to '
        f'{transfer.to_route.route_code}'
    )
    try:
        transfer.delete()
        _log_admin_action(
            request, 'DELETE', 'route_transfers', pk,
            f'Deleted transfer {label}.',
        )
        messages.success(request, f'Transfer "{label}" was deleted.')
    except (IntegrityError, DatabaseError) as exc:
        messages.error(request, _friendly_database_error(exc))
    return redirect('management_route_detail', pk=route_id)


# ---------------------------------------------------------------------------
# Transport and fare categories
# ---------------------------------------------------------------------------

@administrator_required
def transport_type_list(request):
    return render(request, 'management/transport_types.html', {
        'transport_types': TransportationType.objects.annotate(
            route_count=Count('routes')
        ).order_by('transport_name'),
        'supported_modes': SUPPORTED_TRANSPORT_MODES,
    })


@administrator_required
def transport_type_form(request, pk=None):
    instance = get_object_or_404(TransportationType, pk=pk) if pk else None
    form = TransportationTypeForm(
        request.POST or None, instance=instance
    )
    if request.method == 'POST' and form.is_valid():
        transport = form.save()
        _log_admin_action(
            request, 'UPDATE' if pk else 'CREATE', 'transportation_types',
            transport.pk,
            f'{"Updated" if pk else "Created"} transport mode '
            f'"{transport.transport_name}".',
        )
        messages.success(request, 'Transport mode was saved.')
        return redirect('management_transport_types')

    return render(request, 'management/transit_form.html', {
        'form': form,
        'title': 'Edit transport mode' if pk else 'Add transport mode',
        'subtitle': 'Jeepney, bus, van, tricycle and other local modes.',
        'submit_label': 'Save transport mode',
        'cancel_url': reverse('management_transport_types'),
    })


@administrator_required
@require_POST
def transport_type_delete(request, pk):
    transport = get_object_or_404(TransportationType, pk=pk)
    if transport.routes.exists():
        messages.error(
            request,
            f'"{transport.transport_name}" is used by routes. Deactivate it '
            'instead of deleting it.',
        )
    else:
        name = transport.transport_name
        transport.delete()
        _log_admin_action(
            request, 'DELETE', 'transportation_types', pk,
            f'Deleted unused transport mode "{name}".',
        )
        messages.success(request, f'Transport mode "{name}" was deleted.')
    return redirect('management_transport_types')


@administrator_required
def fare_type_list(request):
    return render(request, 'management/fare_types.html', {
        'fare_types': FareType.objects.annotate(
            fare_count=Count('fares')
        ).order_by('fare_type_name'),
    })


@administrator_required
def fare_type_form(request, pk=None):
    instance = get_object_or_404(FareType, pk=pk) if pk else None
    form = FareTypeForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        fare_type = form.save()
        _log_admin_action(
            request, 'UPDATE' if pk else 'CREATE', 'fare_types', fare_type.pk,
            f'{"Updated" if pk else "Created"} fare category '
            f'"{fare_type.fare_type_name}".',
        )
        messages.success(request, 'Fare category was saved.')
        return redirect('management_fare_types')

    return render(request, 'management/transit_form.html', {
        'form': form,
        'title': 'Edit fare category' if pk else 'Add fare category',
        'subtitle': 'Regular, student, senior citizen, PWD and other categories.',
        'submit_label': 'Save fare category',
        'cancel_url': reverse('management_fare_types'),
    })


@administrator_required
@require_POST
def fare_type_delete(request, pk):
    fare_type = get_object_or_404(FareType, pk=pk)
    if fare_type.fares.exists():
        messages.error(
            request,
            f'"{fare_type.fare_type_name}" is used by fare records. Deactivate '
            'it instead of deleting it.',
        )
    else:
        name = fare_type.fare_type_name
        fare_type.delete()
        _log_admin_action(
            request, 'DELETE', 'fare_types', pk,
            f'Deleted unused fare category "{name}".',
        )
        messages.success(request, f'Fare category "{name}" was deleted.')
    return redirect('management_fare_types')


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def _can_manage_user(actor, target):
    """Every administrator may manage every account.

    SakayGuide has a single administrator role, so there is no separate
    super administrator who owns administrator accounts. Self-protection is
    handled separately so an administrator cannot lock themselves out.
    """
    return bool(actor.is_staff)


def _last_active_administrator(target):
    """True when target is the only active administrator account.

    The last administrator can never be deactivated or demoted, otherwise
    nobody would be able to sign in to the management console again.
    """
    return (
        target.is_staff
        and target.is_active
        and User.objects.filter(is_staff=True, is_active=True).count() <= 1
    )


@administrator_required
def user_list(request):
    query = request.GET.get('q', '').strip()
    role = request.GET.get('role', '')
    status = request.GET.get('status', '')

    users_qs = User.objects.all().order_by('-date_joined')
    if query:
        users_qs = users_qs.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if role == 'commuter':
        users_qs = users_qs.filter(is_staff=False)
    elif role == 'administrator':
        # Every staff account is an administrator, including the ones that
        # were originally created as Django superusers.
        users_qs = users_qs.filter(is_staff=True)
    if status == 'active':
        users_qs = users_qs.filter(is_active=True)
    elif status == 'inactive':
        users_qs = users_qs.filter(is_active=False)

    page = _paginate(request, users_qs, TRANSIT_PAGE_SIZE)
    page.object_list = list(page.object_list)
    for user in page.object_list:
        user.management_role = role_for(user)
        user.can_manage = _can_manage_user(request.user, user)
        user.is_self = user.pk == request.user.pk

    return render(request, 'management/users.html', {
        'users': page,
        'query': query,
        'role': role,
        'status': status,
        'total_users': User.objects.count(),
        'total_commuters': User.objects.filter(is_staff=False).count(),
        'total_admins': User.objects.filter(is_staff=True).count(),
        'active_users': User.objects.filter(is_active=True).count(),
        # Every administrator may manage administrator accounts.
        'can_manage_admins': True,
    })


@administrator_required
def user_create(request):
    form = AdminUserCreateForm(request.POST or None, actor=request.user)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        _sync_user_mirror(user)
        log_activity(
            request.user,
            'CREATE',
            'users',
            record_id=user.pk,
            description=(
                f'Created {role_for(user)} account "{user.username}" '
                f'({user.email or "no e-mail"}).'
            ),
        )
        messages.success(
            request,
            f'User "{user.username}" was created as a {role_for(user)}.',
        )
        return redirect('management_users')

    return render(request, 'management/user_form.html', {
        'form': form,
        'mode': 'create',
        'target': None,
        # Every administrator may create administrator accounts.
        'can_manage_admins': True,
    })


@administrator_required
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    if not _can_manage_user(request.user, target):
        messages.error(
            request,
            'Administrator access is required to manage that account.',
        )
        return redirect('management_users')

    form = AdminUserEditForm(
        request.POST or None,
        actor=request.user,
        target=target,
    )
    if request.method == 'POST' and form.is_valid():
        proposed_role = form.cleaned_data['role']
        proposed_active = bool(form.cleaned_data.get('is_active'))
        error = None

        if target.pk == request.user.pk:
            if not proposed_active:
                error = 'You cannot deactivate your own account.'
            elif target.is_staff and proposed_role == 'commuter':
                error = 'You cannot remove your own administrator access.'

        if (
            error is None
            and target.is_staff
            and target.is_active
            and (proposed_role != 'administrator' or not proposed_active)
            and User.objects.filter(
                is_staff=True, is_active=True
            ).count() <= 1
        ):
            error = 'At least one active administrator must remain.'

        if error:
            form.add_error(None, error)
        else:
            password_changed = bool(form.cleaned_data.get('password'))
            user = form.save()
            _sync_user_mirror(user)
            if user.pk == request.user.pk and password_changed:
                update_session_auth_hash(request, user)
            log_activity(
                request.user,
                'UPDATE',
                'users',
                record_id=user.pk,
                description=(
                    f'Updated {role_for(user)} account "{user.username}" '
                    f'(active={user.is_active}).'
                ),
            )
            messages.success(request, f'User "{user.username}" was updated.')
            return redirect('management_users')

    return render(request, 'management/user_form.html', {
        'form': form,
        'mode': 'edit',
        'target': target,
        # Every administrator may manage administrator accounts.
        'can_manage_admins': True,
    })


@administrator_required
@require_POST
def user_toggle(request, pk):
    target = get_object_or_404(User, pk=pk)
    if not _can_manage_user(request.user, target):
        messages.error(
            request,
            'Administrator access is required to change that account.',
        )
        return redirect('management_users')
    if target.pk == request.user.pk:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('management_users')
    if _last_active_administrator(target):
        messages.error(
            request, 'At least one active administrator must remain.'
        )
        return redirect('management_users')

    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    _sync_user_mirror(target)
    log_activity(
        request.user,
        'ACTIVATE' if target.is_active else 'DEACTIVATE',
        'users',
        record_id=target.pk,
        description=(
            f'{"Activated" if target.is_active else "Deactivated"} account '
            f'"{target.username}".'
        ),
    )
    messages.success(
        request,
        f'User "{target.username}" is now '
        f'{"active" if target.is_active else "inactive"}.',
    )
    return redirect('management_users')


# ---------------------------------------------------------------------------
# Map management
# ---------------------------------------------------------------------------

@administrator_required
def map_management(request):
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    missing = request.GET.get('missing', '')
    route_id = request.GET.get('route', '')

    locations = Location.objects.select_related('barangay').order_by(
        'location_name'
    )
    if query:
        locations = locations.filter(
            Q(location_name__icontains=query)
            | Q(barangay__barangay_name__icontains=query)
            | Q(address__icontains=query)
        )
    if status in ('active', 'inactive'):
        locations = locations.filter(status=status)
    if missing == '1':
        locations = locations.filter(
            Q(latitude__isnull=True) | Q(longitude__isnull=True)
        )
    elif missing == '0':
        locations = locations.filter(
            latitude__isnull=False, longitude__isnull=False,
        )

    locations = list(locations)
    markers = [_location_marker(location) for location in locations]

    selected_route = None
    if route_id:
        selected_route = get_object_or_404(
            Route.objects.select_related(
                'origin', 'destination', 'transport_type'
            ),
            pk=route_id,
        )

    return render(request, 'management/map.html', {
        'markers': markers,
        'locations': locations,
        'missing_locations': [
            location for location in locations if _coords(location) is None
        ],
        'routes': Route.objects.select_related(
            'origin', 'destination'
        ).order_by('route_code'),
        'selected_route': selected_route,
        'route_map_data': _route_map_payload(selected_route),
        'google_maps': _google_maps_config(),
        'query': query,
        'status': status,
        'missing': missing,
        'route_id': route_id,
        'mapped_count': sum(1 for item in markers if item['has_coords']),
        'missing_count': sum(1 for item in markers if not item['has_coords']),
    })


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

@administrator_required
def activity(request):
    query = request.GET.get('q', '').strip()
    action_type = request.GET.get('action', '')
    table = request.GET.get('table', '')

    logs = AdminActivityLog.objects.select_related('admin')
    if query:
        logs = logs.filter(
            Q(action_description__icontains=query)
            | Q(admin__full_name__icontains=query)
            | Q(admin__email__icontains=query)
            | Q(table_affected__icontains=query)
        )
    if action_type:
        logs = logs.filter(action_type=action_type)
    if table:
        logs = logs.filter(table_affected=table)
    logs = logs.order_by('-created_at', '-log_id')

    searches = SearchHistory.objects.select_related(
        'user', 'origin', 'destination'
    )
    if query:
        searches = searches.filter(
            Q(user__full_name__icontains=query)
            | Q(origin__location_name__icontains=query)
            | Q(destination__location_name__icontains=query)
        )
    searches = searches.order_by('-search_date', '-search_id')

    recent_locations = Location.objects.select_related('barangay').order_by(
        '-location_id'
    )[:10]

    return render(request, 'management/activity.html', {
        'logs': _paginate(request, logs, TRANSIT_PAGE_SIZE),
        'searches': _paginate(
            request, searches, TRANSIT_PAGE_SIZE, page_param='search_page'
        ),
        'recent_locations': recent_locations,
        'query': query,
        'action_type': action_type,
        'table': table,
        'action_choices': AdminActivityLog.objects.values_list(
            'action_type', flat=True
        ).distinct().order_by('action_type'),
        'table_choices': AdminActivityLog.objects.values_list(
            'table_affected', flat=True
        ).distinct().order_by('table_affected'),
        'total_logs': AdminActivityLog.objects.count(),
        'total_searches': SearchHistory.objects.count(),
    })


# ---------------------------------------------------------------------------
# Route search monitoring
# ---------------------------------------------------------------------------

@administrator_required
def search_monitoring(request):
    """Monitor every route search the commuters make.

    Administrators can see which pairs are being searched, how often and by
    whom, so they know which routes, stops and fares need attention. The
    list is read-only: administrators never edit a commuter's search from
    here, and commuters never reach this page.
    """
    query = request.GET.get('q', '').strip()
    window = request.GET.get('window', '')
    audience = request.GET.get('audience', '')

    searches = SearchHistory.objects.select_related(
        'user', 'origin', 'destination'
    )

    if query:
        searches = searches.filter(
            Q(user__full_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(origin__location_name__icontains=query)
            | Q(destination__location_name__icontains=query)
        )
    if window == '7':
        searches = searches.filter(
            search_date__date__gte=timezone.localdate() - timedelta(days=6)
        )
    elif window == '30':
        searches = searches.filter(
            search_date__date__gte=timezone.localdate() - timedelta(days=29)
        )
    elif window == 'guest':
        searches = searches.filter(user__isnull=True)
    elif window == 'commuter':
        searches = searches.filter(user__isnull=False)

    searches = searches.order_by('-search_date', '-search_id')
    page = _paginate(request, searches, TRANSIT_PAGE_SIZE)

    total = SearchHistory.objects.count()
    guest_total = SearchHistory.objects.filter(user__isnull=True).count()
    week_total = SearchHistory.objects.filter(
        search_date__date__gte=timezone.localdate() - timedelta(days=6)
    ).count()

    top_pairs = list(
        SearchHistory.objects.values(
            'origin__location_name', 'destination__location_name'
        ).annotate(count=Count('search_id')).order_by('-count')[:8]
    )

    return render(request, 'management/searches.html', {
        'searches': page,
        'query': query,
        'window': window,
        'audience': audience,
        'total_searches': total,
        'guest_searches': guest_total,
        'commuter_searches': total - guest_total,
        'week_searches': week_total,
        'top_pairs': top_pairs,
    })


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@administrator_required
def reports(request):
    """Management reports built from the recorded SakayGuide data."""
    today = timezone.localdate()
    week_start = today - timedelta(days=6)
    month_start = today - timedelta(days=29)

    stats = {
        'total_users': User.objects.count(),
        'total_commuters': User.objects.filter(is_staff=False).count(),
        'total_admins': User.objects.filter(is_staff=True).count(),
        'new_users_week': User.objects.filter(
            date_joined__date__gte=week_start,
        ).count(),
        'new_users_month': User.objects.filter(
            date_joined__date__gte=month_start,
        ).count(),
    }

    try:
        stats.update({
            'total_routes': Route.objects.count(),
            'active_routes': Route.objects.filter(status='active').count(),
            'total_stops': RouteStop.objects.count(),
            'total_locations': Location.objects.count(),
            'active_locations': Location.objects.filter(status='active').count(),
            'locations_with_coords': Location.objects.filter(
                latitude__isnull=False, longitude__isnull=False,
            ).count(),
            'total_fares': RouteFare.objects.count(),
            'active_fares': RouteFare.objects.filter(status='active').count(),
            'total_searches': SearchHistory.objects.count(),
            'searches_week': SearchHistory.objects.filter(
                search_date__date__gte=week_start,
            ).count(),
            'searches_month': SearchHistory.objects.filter(
                search_date__date__gte=month_start,
            ).count(),
            'guest_searches': SearchHistory.objects.filter(
                user__isnull=True,
            ).count(),
            'saved_routes': SavedRoute.objects.count(),
            'activity_logs': AdminActivityLog.objects.count(),
        })

        stats['coverage_percent'] = (
            round(
                stats['locations_with_coords'] * 100
                / stats['active_locations']
            )
            if stats['active_locations'] else 0
        )

        stats['mode_report'] = list(
            TransportationType.objects.annotate(
                route_count=Count('routes'),
                active_route_count=Count(
                    'routes', filter=Q(routes__status='active')
                ),
            ).order_by('-active_route_count', 'transport_name')
        )

        stats['fare_report'] = list(
            RouteFare.objects.filter(status='active')
            .values('fare_type__fare_type_name')
            .annotate(
                count=Count('fare_id'),
                average=Avg('total_estimated_fare'),
                lowest=Min('total_estimated_fare'),
                highest=Max('total_estimated_fare'),
            ).order_by('fare_type__fare_type_name')
        )

        stats['top_destinations'] = list(
            SearchHistory.objects.values('destination__location_name')
            .annotate(count=Count('search_id'))
            .order_by('-count')[:8]
        )
        stats['top_origins'] = list(
            SearchHistory.objects.values('origin__location_name')
            .annotate(count=Count('search_id'))
            .order_by('-count')[:8]
        )
        stats['search_activity'] = list(
            SearchHistory.objects.filter(
                search_date__date__gte=week_start
            ).values('search_date__date').annotate(count=Count('search_id'))
        )
    except DatabaseError:
        stats['db_error'] = (
            'The SakayGuide transit database is unavailable, so the transit '
            'reports could not be generated.'
        )

    return render(request, 'management/reports.html', {'stats': stats})

