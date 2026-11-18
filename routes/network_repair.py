"""Network data repairs for the live SakayGuide database.

The live database contains three data faults that make valid trips
unsearchable:

* locations 20-42 were renamed with another barangay's name, so the search
  results showed the wrong place for a route stop (their barangay foreign
  keys and coordinates were always correct);
* the 32 ``KAB-JP-0xx`` jeepney routes point at sequential place IDs instead
  of the barangay named in the route title (and ``KAB-JP-002`` therefore has
  the same origin and destination);
* those 32 routes, plus the city-loop route, have no ``route_stops`` rows for
  their recorded origin/destination.

Everything below is derived from rows already in the database - the barangay
foreign key, the route title and the route's recorded endpoints. No new route,
stop, fare or travel time is invented. The functions are idempotent and are
shared by the ``repair_sakayguide_network`` management command and the
administration route form.
"""
import re

from django.db import transaction
from django.db.models import F

from .models import Barangay, Location, Route, RouteStop

# "Public Terminal - Binicuil Jeepney" -> origin "Public Terminal",
# destination "Binicuil". Only applied to the three-digit KAB-JP route codes
# whose titles were affected; newer/admin routes are left untouched.
_ROUTE_TITLE_RE = re.compile(
    r'^\s*(?P<origin>.+?)\s+-\s+(?P<destination>.+?)\s+Jeepney\s*$',
    re.IGNORECASE,
)
_AFFECTED_ROUTE_CODE_RE = re.compile(r'^KAB-JP-\d{3}$')


def _active_locations_by_name():
    """Map case-folded location names to active locations.

    Barangay records win over same-named non-barangay places because the
    route titles refer to barangays.
    """
    by_name = {}
    rows = Location.objects.filter(status='active').select_related('barangay')
    for location in rows:
        key = location.location_name.strip().casefold()
        current = by_name.get(key)
        if current is None or (
            location.location_type == 'barangay'
            and current.location_type != 'barangay'
        ):
            by_name[key] = location
    return by_name


def repair_location_names(apply=True):
    """Restore barangay locations whose name belongs to a different barangay.

    A location is repaired only when its current name is the name of another
    barangay. That catches the rotated 20-42 block without touching places
    that legitimately carry a custom name. Returns a list of
    ``(location_id, old_name, new_name)`` changes.
    """
    barangay_by_name = {
        barangay.barangay_name.strip().casefold(): barangay
        for barangay in Barangay.objects.all()
    }
    changes = []
    locations = (
        Location.objects.filter(location_type='barangay')
        .select_related('barangay')
        .order_by('location_id')
    )
    for location in locations:
        own_name = location.barangay.barangay_name.strip()
        current_name = location.location_name.strip()
        if current_name.casefold() == own_name.casefold():
            continue
        name_owner = barangay_by_name.get(current_name.casefold())
        if name_owner is None or name_owner.pk == location.barangay_id:
            continue
        changes.append((location.location_id, location.location_name, own_name))
        if apply:
            location.location_name = own_name
            location.save(update_fields=['location_name'])
    return changes


def repair_route_endpoints(apply=True):
    """Point affected route endpoints at the places named by the route title.

    Returns ``(route_id, old_origin, new_origin, old_destination,
    new_destination)`` tuples only for routes that changed (or would change
    in dry-run mode).
    """
    locations_by_name = _active_locations_by_name()
    changes = []
    routes = (
        Route.objects.filter(status='active')
        .select_related('origin', 'destination')
        .order_by('route_code')
    )
    for route in routes:
        if not _AFFECTED_ROUTE_CODE_RE.match(route.route_code):
            continue
        match = _ROUTE_TITLE_RE.match(route.route_name)
        if not match:
            continue
        origin = locations_by_name.get(match.group('origin').strip().casefold())
        destination = locations_by_name.get(
            match.group('destination').strip().casefold()
        )
        if origin is None or destination is None or origin.pk == destination.pk:
            continue
        if route.origin_id == origin.pk and route.destination_id == destination.pk:
            continue
        changes.append((
            route.route_id,
            route.origin.location_name,
            origin.location_name,
            route.destination.location_name,
            destination.location_name,
        ))
        if apply:
            route.origin = origin
            route.destination = destination
            route.save(update_fields=['origin', 'destination'])
    return changes


def _shift_stop_orders(route, delta):
    """Move every stop order by ``delta`` without violating uniqueness."""
    RouteStop.objects.filter(route=route).update(
        stop_order=F('stop_order') + 1000,
    )
    RouteStop.objects.filter(route=route).update(
        stop_order=F('stop_order') + delta - 1000,
    )


def ensure_route_stops(route, apply=True):
    """Make the recorded origin and destination actual ordered stops.

    Existing stops are preserved in their recorded order; a missing origin is
    prepended and a missing destination appended. A route with no stops gets
    exactly its two recorded endpoints. Returns human-readable action strings.
    """
    if route.origin_id == route.destination_id:
        return []

    stops = list(route.stops.order_by('stop_order'))
    actions = []

    if not stops:
        actions.append(
            f'added origin {route.origin.location_name} (order 1)'
        )
        actions.append(
            f'added destination {route.destination.location_name} '
            f'(order 2)'
        )
        if apply:
            RouteStop.objects.bulk_create([
                RouteStop(
                    route=route,
                    location=route.origin,
                    stop_order=1,
                    is_transfer_point=True,
                    estimated_stop_time=0,
                ),
                RouteStop(
                    route=route,
                    location=route.destination,
                    stop_order=2,
                    is_transfer_point=True,
                    estimated_stop_time=route.estimated_travel_time,
                ),
            ])
        return actions

    location_ids = {stop.location_id for stop in stops}
    max_order = max(stop.stop_order for stop in stops)

    if route.origin_id not in location_ids:
        actions.append(
            f'added origin {route.origin.location_name} (order 1, '
            f'{len(stops)} existing stops shifted)'
        )
        if apply:
            _shift_stop_orders(route, 1)
            RouteStop.objects.create(
                route=route,
                location=route.origin,
                stop_order=1,
                is_transfer_point=True,
                estimated_stop_time=0,
            )
        max_order += 1

    if route.destination_id not in location_ids:
        actions.append(
            f'added destination {route.destination.location_name} '
            f'(order {max_order + 1})'
        )
        if apply:
            RouteStop.objects.create(
                route=route,
                location=route.destination,
                stop_order=max_order + 1,
                is_transfer_point=True,
                estimated_stop_time=route.estimated_travel_time,
            )

    return actions


def repair_all_route_stops(apply=True):
    """Run :func:`ensure_route_stops` for every active route."""
    results = []
    routes = (
        Route.objects.filter(status='active')
        .select_related('origin', 'destination')
        .order_by('route_code')
    )
    for route in routes:
        actions = ensure_route_stops(route, apply=apply)
        if actions:
            results.append((route.route_code, actions))
    return results


def routes_without_active_regular_fare():
    """Active routes that still have no active regular fare row.

    The repair never creates a fare: a missing fare must stay visibly
    "not recorded" rather than being guessed.
    """
    return list(
        Route.objects.filter(status='active')
        .exclude(
            fares__fare_type_id=1,
            fares__status='active',
        )
        .order_by('route_code')
    )


def repair_network(apply=True):
    """Apply the complete, idempotent network repair."""
    if apply:
        with transaction.atomic(using='sakayguide'):
            return _repair_network(apply=True)
    return _repair_network(apply=False)


def _repair_network(apply):
    return {
        'location_names': repair_location_names(apply=apply),
        'route_endpoints': repair_route_endpoints(apply=apply),
        'route_stops': repair_all_route_stops(apply=apply),
        'routes_without_fare': routes_without_active_regular_fare(),
    }
