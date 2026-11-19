"""Route-search logic for the "Where do you want to go?" feature.

Everything here is computed from records already stored in sakayguide_db
(routes, route_stops, route_fares, route_transfers, locations.latitude /
locations.longitude). Nothing is invented:

* a journey is either one continuous ride, or two rides joined by a
  recorded ``route_transfers`` connection (one change of vehicle at the
  recorded transfer point). A route can be ridden in either direction;
* the map payload carries exactly two pins - the starting point (green) and
  the destination (red) - plus the route's road geometry as one continuous
  blue path; no intermediate stop, transfer point or landmark markers are
  drawn;
* when a route has no ``route_stops`` rows its recorded origin and destination
  are used as the two endpoint stops - the route record itself asserts those
  places are served;
* when coordinates are missing for an endpoint the place stays in the
  journey instructions and is reported as "map position not yet verified";
* every fare is read from the latest *currently effective* active
  ``route_fares`` row for the route and fare category. The stored
  ``total_estimated_fare`` is authoritative for the full route; a partial
  segment is scaled by its share of the recorded route distance and never
  drops below the stored ``minimum_fare``. No amount is hard-coded;
* travel time is based on the travelled distance: the route's recorded
  full-route ``estimated_travel_time`` is apportioned over its measured
  full-route distance, so a shorter origin/destination pair takes
  proportionally less time. When a route's stop list is not ordered like the
  vehicle's path (its measured length far exceeds the straight line between
  its endpoints), the distance between the board and alight points is used
  instead of the impossible zig-zag total;
* fares and times are labelled as provisional estimates by the presentation
  layer, and a leg whose route has no active regular fare record is reported
  as "fare not recorded" rather than being given a guessed amount.
"""
import hashlib
from decimal import Decimal, ROUND_HALF_UP
from math import asin, cos, radians, sin, sqrt

from django.db.models import Count
from django.utils import timezone

from .models import (
    BARANGAY_LOCATION_TYPE,
    Location,
    Route,
    RouteFare,
    RouteStop,
    RouteTransfer,
    SearchHistory,
)

# Regular fare type (fare_types.fare_type_id = 1) is used for estimates.
REGULAR_FARE_TYPE_ID = 1

# Discounted fare types used for the Student/PWD prices: fare_types.fare_type_id
# 2 = Student (20%), 4 = Person with Disability (20%). The student record is
# preferred when a route carries both; PWD is used as a fallback. Senior
# Citizen (3) is also a 20% record on every route but is intentionally not
# folded in here, so the commuter sees exactly the two prices that were
# requested.
DISCOUNT_FARE_TYPE_IDS = (2, 4)

# Find My Route presents direct rides and one-transfer journeys built from
# the recorded ``route_transfers`` connections. The number of options for one
# pair is small (a handful of routes can serve the same pair); no artificial
# cap is applied, and no connection is invented.

# A stop list whose measured path is much longer than the straight line
# between the route's own endpoints is ordered by data entry, not by the
# vehicle's journey (for example the barangays stored alphabetically on
# KAB-JP-07). Time and distance then use the straight-line distance between
# the board and alight points instead of an impossible zig-zag total.
MAX_ROUTE_DETOUR_RATIO = 4.0

# Distinct shades of blue, one per ride. The map draws every ride path in
# blue; later rides use lighter/darker blues so a multi-ride journey stays
# readable without leaving the blue family.
LEG_COLORS = ('#1c7ed6', '#0b5ed7', '#4dabf7')

# Kabankalan City poblacion (OpenStreetMap, October 2026). Used only as
# the "no markers to fit" default view, never to fake coordinates.
KABANKALAN_CENTER = (9.9926, 122.8135)
FALLBACK_ZOOM = 12

EARTH_RADIUS_KM = 6371.0088


def _haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two WGS 84 points, in kilometres."""
    lat1, lng1, lat2, lng2 = (
        radians(float(lat1)), radians(float(lng1)),
        radians(float(lat2)), radians(float(lng2)),
    )
    d_lat = lat2 - lat1
    d_lng = lng2 - lng1
    a = (
        sin(d_lat / 2) * sin(d_lat / 2)
        + cos(lat1) * cos(lat2) * sin(d_lng / 2) * sin(d_lng / 2)
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def _distance_km_for_stops(stops):
    """Distance along an ordered list of stop dicts with ``location`` keys.

    Missing coordinates simply skip that point; the remaining verified
    points are still measured in order. Returns ``0.0`` when fewer than two
    verified points exist (never guesses a distance).
    """
    distance = 0.0
    previous = None
    for entry in stops:
        location = entry.get('location')
        coordinate = _coord(location)
        if coordinate is None:
            continue
        if previous is not None:
            distance += _haversine_km(
                previous[0], previous[1], coordinate[0], coordinate[1],
            )
        previous = coordinate
    return round(distance, 2)


def _endpoint_stop(location, order, time):
    """An in-memory stop entry for a recorded route origin/destination.

    Mirrors the stop rows written by the network repair command and by the
    administration route form, so a route that exists but has not been given
    its stop list yet still appears in the search instead of being dropped.
    """
    return {
        'stop': None,
        'location': location,
        'location_id': location.location_id,
        'order': order,
        'time': time,
        'name': location.location_name,
        'is_transfer': True,
    }


# ---------------------------------------------------------------------------
# Current fare resolution (single source of truth for every commuter display)
# ---------------------------------------------------------------------------
def fare_is_current(fare, today=None):
    """Whether an active fare row applies today.

    A row applies when it is active, its effective date has arrived and it
    has not expired. These are the same rules the administrator's fare
    history uses, so the commuter and the management console always agree.
    """
    if fare.status != RouteFare.STATUS_ACTIVE:
        return False
    today = today or timezone.localdate()
    if fare.effective_date and fare.effective_date > today:
        return False
    if fare.expiry_date and fare.expiry_date < today:
        return False
    return True


def latest_active_fares(fares, today=None):
    """Pick the latest current fare row per ``(route, fare_type)``.

    ``fares`` is any iterable of ``RouteFare`` rows (a queryset, a prefetch
    cache or a plain list). When more than one active row exists for the same
    route and category the one with the newest effective date - and, on a
    tie, the newest primary key - wins. That keeps the admin console from
    ever leaving two active records that could disagree.
    """
    today = today or timezone.localdate()
    selected = {}
    for fare in fares:
        if not fare_is_current(fare, today):
            continue
        key = (fare.route_id, fare.fare_type_id)
        current = selected.get(key)
        if current is None or (
            fare.effective_date, fare.fare_id
        ) > (
            current.effective_date, current.fare_id
        ):
            selected[key] = fare
    return selected


def current_fare_map(fare_type_ids=None, route_ids=None):
    """``{(route_id, fare_type_id): fare}`` for every currently active fare."""
    fares = RouteFare.objects.all()
    if fare_type_ids is not None:
        fares = fares.filter(fare_type_id__in=fare_type_ids)
    if route_ids is not None:
        fares = fares.filter(route_id__in=route_ids)
    return latest_active_fares(fares)


def fares_version():
    """Short fingerprint of every currently effective fare amount.

    Used by the commuter pages to notice, without reloading, that the
    administrator saved a new fare. Editing an amount, adding a category,
    deleting a record or expiring one all change the fingerprint.
    """
    rows = RouteFare.objects.values_list(
        'fare_id', 'route_id', 'fare_type_id', 'minimum_fare',
        'fare_per_km', 'total_estimated_fare', 'effective_date', 'expiry_date',
    ).order_by('fare_id')
    today = timezone.localdate()
    parts = []
    for (fare_id, route_id, fare_type_id, minimum, per_km, total,
         effective, expiry) in rows:
        if effective and effective > today:
            continue
        if expiry and expiry < today:
            continue
        parts.append(
            f'{fare_id}:{route_id}:{fare_type_id}:{minimum}:{per_km}:'
            f'{total}:{effective}:{expiry}'
        )
    return hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()[:16]


def _segment_minutes(full_minutes, segment_distance_km, route_distance_km):
    """Travel time for one travelled segment, proportional to its distance.

    The route's recorded ``estimated_travel_time`` is the authoritative
    full-route duration (a full-length segment always returns it unchanged).
    A shorter segment takes the same share of that time as its share of the
    route's measured distance, rounded to the nearest minute, and never less
    than one minute. The time therefore follows the distance the commuter
    actually travels on the recorded route.
    """
    full_minutes = int(full_minutes or 0)
    if full_minutes <= 0:
        return 0
    if route_distance_km <= 0:
        return full_minutes

    ratio = max(float(segment_distance_km), 0.0) / float(route_distance_km)
    if ratio >= 1:
        return full_minutes
    minutes = int(ratio * full_minutes + 0.5)
    return max(1, minutes)


def _segment_fare(fare_record, segment_distance_km, route_distance_km):
    """Fare for one travelled segment of a route, from its stored fare row.

    ``total_estimated_fare`` is the authoritative amount for the full route
    (a full-length segment always returns it unchanged). A shorter segment is
    charged the same share of the stored total as its share of the route's
    recorded ``minimum_fare + fare_per_km * distance`` pricing, so the
    administrator's per-kilometre rate genuinely lowers the price for a
    shorter trip. When no per-kilometre rate is recorded the share is the
    plain distance share.

    The result is never below ``minimum_fare`` and never above the full-route
    total, so the administrator's values are always the source of truth.
    """
    if fare_record is None:
        return None
    total = Decimal(fare_record.total_estimated_fare or 0)
    minimum = Decimal(fare_record.minimum_fare or 0)
    per_km = Decimal(fare_record.fare_per_km or 0)
    if total <= 0 or route_distance_km <= 0:
        return total

    segment = Decimal(str(max(float(segment_distance_km), 0.0)))
    full = Decimal(str(float(route_distance_km)))
    if segment >= full:
        return total

    if per_km > 0:
        full_formula = minimum + per_km * full
        segment_formula = minimum + per_km * segment
        amount = total * (segment_formula / full_formula)
    else:
        amount = total * (segment / full)

    amount = min(amount, total)
    floor = min(minimum, total)
    if amount < floor:
        amount = floor
    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Loading the active network
# ---------------------------------------------------------------------------
def _load_network():
    """Load the active slice of the network into cheap in-memory indexes."""
    routes = {
        r.pk: r
        for r in Route.objects.filter(status='active').select_related(
            'transport_type', 'origin', 'destination'
        )
    }

    stops_by_route = {}
    for s in RouteStop.objects.filter(route_id__in=routes).select_related(
        'location'
    ).order_by('route_id', 'stop_order'):
        stops_by_route.setdefault(s.route_id, []).append({
            'stop': s,
            'location': s.location,
            'location_id': s.location_id,
            'order': s.stop_order,
            'time': s.estimated_stop_time,
            'name': s.location.location_name,
            'is_transfer': s.is_transfer_point,
        })

    # A route whose stop list is missing (or which is missing one of its
    # recorded endpoints) is still usable: the route record itself asserts
    # the origin and destination are served. The endpoints are added in
    # memory exactly as the repair command records them, so a route created
    # before its stops are entered is never excluded from the search.
    for route_id, route in routes.items():
        entries = stops_by_route.setdefault(route_id, [])
        known_ids = {entry['location_id'] for entry in entries}
        if not entries:
            if route.origin_id == route.destination_id:
                entries.append(_endpoint_stop(route.origin, 1, 0))
            else:
                entries.append(_endpoint_stop(route.origin, 1, 0))
                entries.append(_endpoint_stop(
                    route.destination, 2, route.estimated_travel_time,
                ))
            continue
        if route.origin_id not in known_ids:
            for entry in entries:
                entry['order'] += 1
            entries.insert(0, _endpoint_stop(route.origin, 1, 0))
            known_ids.add(route.origin_id)
        if (
            route.destination_id not in known_ids
            and route.destination_id != route.origin_id
        ):
            entries.append(_endpoint_stop(
                route.destination, len(entries) + 1,
                route.estimated_travel_time,
            ))

    order_index = {
        rid: {entry['location_id']: i for i, entry in enumerate(entries)}
        for rid, entries in stops_by_route.items()
    }

    # Distance along each recorded route, used to scale a segment's fare and
    # time. A stop list may be stored in an order that does not follow the
    # vehicle's actual path (for example alphabetically). When its measured
    # length is far beyond the straight line between the route's endpoints,
    # the segment is measured straight between board and alight instead.
    route_distances = {
        rid: _distance_km_for_stops(entries)
        for rid, entries in stops_by_route.items()
    }
    route_straight_distances = {}
    straight_distance_routes = set()
    for route_id, route in routes.items():
        origin_coord = _coord(route.origin)
        destination_coord = _coord(route.destination)
        straight_km = 0.0
        if origin_coord and destination_coord:
            straight_km = round(_haversine_km(
                origin_coord[0], origin_coord[1],
                destination_coord[0], destination_coord[1],
            ), 2)
        route_straight_distances[route_id] = straight_km
        along_km = route_distances.get(route_id, 0.0)
        if (
            straight_km > 0
            and along_km > straight_km * MAX_ROUTE_DETOUR_RATIO
        ):
            straight_distance_routes.add(route_id)

    # Current regular and discounted fares, resolved through one helper so
    # the journey engine, the dashboard cards and the search panel can never
    # disagree about which saved amount is the latest.
    current = latest_active_fares(RouteFare.objects.filter(
        route_id__in=routes,
        fare_type_id__in=(REGULAR_FARE_TYPE_ID, *DISCOUNT_FARE_TYPE_IDS),
    ).order_by('effective_date', 'fare_id'))

    fares = {
        route_id: fare
        for (route_id, fare_type_id), fare in current.items()
        if fare_type_id == REGULAR_FARE_TYPE_ID
    }
    # Student (2) is preferred when a route carries both discounted records;
    # PWD (4) is used as a fallback. A route with no discounted record is
    # reported as "not recorded" - never given a computed guess.
    student_fares = {}
    for fare_type_id in DISCOUNT_FARE_TYPE_IDS:
        for (route_id, current_type_id), fare in current.items():
            if current_type_id == fare_type_id:
                student_fares.setdefault(route_id, fare)

    # Recorded one-transfer connections between active routes, indexed by
    # the first ride. Each row is one real, administrator-managed transfer.
    transfers_from = {}
    for transfer in RouteTransfer.objects.filter(
        from_route_id__in=routes,
        to_route_id__in=routes,
    ).select_related('to_route', 'transfer_location').order_by('transfer_id'):
        transfers_from.setdefault(transfer.from_route_id, []).append(transfer)

    return (
        routes, stops_by_route, order_index, fares, student_fares,
        route_distances, route_straight_distances, straight_distance_routes,
        transfers_from,
    )


# ---------------------------------------------------------------------------
# Journey building
# ---------------------------------------------------------------------------
def _make_leg(route_id, from_location_id, to_location_id, ctx):
    """Build one ride (leg) of a journey between two stops of one route.

    The recorded stop list can be travelled in either direction, so the
    segment is reversed when the destination comes before the origin on the
    stored route. The intermediate stops are deliberately *not* copied into
    the journey payload: the commuter only sees the starting point, the
    destination and one continuous ride.

    Travel time is based on the distance of the travelled segment: the
    route's recorded full-route ``estimated_travel_time`` is apportioned
    across its measured full-route distance, so boarding or alighting at a
    different stop recalculates the minutes. A stop list recorded in an order
    that does not follow the vehicle's path is measured straight between the
    board and alight points, so an alphabetical barangay list cannot collapse
    a 12 km hop to one minute. When no coordinates are recorded the
    cumulative stop times are used as a fallback.

    The fare is the segment's share of the latest active full-route fare, so
    changing the starting point or destination recalculates the amount while
    the administrator's saved full-route total stays authoritative.
    """
    (
        routes, stops_by_route, order_index, fares, student_fares,
        route_distances, route_straight_distances, straight_distance_routes,
        _transfers,
    ) = ctx
    index = order_index[route_id]
    i, j = index[from_location_id], index[to_location_id]
    forward = i <= j
    if forward:
        segment = stops_by_route[route_id][i:j + 1]
    else:
        segment = list(reversed(stops_by_route[route_id][j:i + 1]))
    start, end = segment[0], segment[-1]

    if route_id in straight_distance_routes:
        # The recorded stop order zig-zags (it is not the travel path), so
        # the segment is measured directly between the two points the
        # commuter boards and alights at.
        board_coord = _coord(start['location'])
        alight_coord = _coord(end['location'])
        if board_coord and alight_coord:
            distance_km = round(_haversine_km(
                board_coord[0], board_coord[1],
                alight_coord[0], alight_coord[1],
            ), 2)
        else:
            distance_km = 0.0
        full_distance_km = route_straight_distances.get(route_id, 0.0)
    else:
        distance_km = _distance_km_for_stops(segment)
        full_distance_km = route_distances.get(route_id, 0.0)
    full_minutes = routes[route_id].estimated_travel_time or 0

    # Time follows distance: spread the recorded full-route duration over the
    # measured full-route distance and charge the segment its proportional
    # share. A full-length segment returns the route's saved duration exactly.
    minutes = _segment_minutes(full_minutes, distance_km, full_distance_km)
    if minutes <= 0:
        # No recorded time or no verified coordinates: fall back to the
        # recorded cumulative stop times, then to the route's estimate.
        minutes = abs(end['time'] - start['time'])
    if minutes <= 0:
        minutes = full_minutes

    fare_record = fares.get(route_id)
    # A route without an active regular fare record must never be shown with
    # a guessed amount; the presentation layer reports "fare not recorded".
    fare = _segment_fare(fare_record, distance_km, full_distance_km)
    discount_fare_record = student_fares.get(route_id)
    discount_fare = _segment_fare(
        discount_fare_record, distance_km, full_distance_km,
    )

    return {
        'route': routes[route_id],
        'route_id': route_id,
        'board_at': start['name'],
        'alight_at': end['name'],
        'board_id': from_location_id,
        'alight_id': to_location_id,
        'minutes': minutes,
        'distance_km': distance_km,
        'fare': fare,
        'fare_record': fare_record,
        'fare_recorded': fare_record is not None,
        'fare_discount': discount_fare,
        'discount_fare_recorded': discount_fare_record is not None,
        'forward': forward,
    }


def _build_steps(origin_name, destination_name, legs, transfers):
    """Generate the step-by-step 'Your Journey' instructions.

    A direct ride is board-and-alight. When the journey changes vehicle the
    recorded transfer instructions and waiting time are inserted between the
    two rides, so the commuter knows exactly where to alight and board again.
    """
    steps = [f'Start at {origin_name}.']
    for leg_index, leg in enumerate(legs):
        route = leg['route']
        mode = route.transport_type.transport_name.lower()
        steps.append(
            f'Board the {mode} {route.route_code} ({route.route_name}) '
            f'at {leg["board_at"]}.'
        )
        if leg_index < len(legs) - 1:
            steps.append(
                f'Ride to {leg["alight_at"]} and alight there.'
            )
            transfer = transfers[leg_index] if leg_index < len(transfers) else None
            if transfer:
                wait = transfer.get('time') or 0
                steps.append(
                    f'Transfer at {transfer["location_name"]} to '
                    f'{transfer["to_code"]}. {transfer["instructions"]}'
                    + (f' Allow about {wait} minutes.' if wait else '')
                )
        else:
            steps.append(f'Ride to {leg["alight_at"]}.')
    if not legs or legs[-1]['alight_at'] != destination_name:
        steps.append(f'Get off at {destination_name}.')
    return steps


# ---------------------------------------------------------------------------
# Map payloads (consumed by static/js/route-map.js via JSON)
# ---------------------------------------------------------------------------
def _coord(location):
    """Return [lat, lng] for a Location with verified coordinates, else None."""
    if location is None or location.latitude is None or location.longitude is None:
        return None
    return [float(location.latitude), float(location.longitude)]


def _endpoint_dict(location):
    """Origin/destination marker descriptor for a map payload."""
    coord = _coord(location)
    suffix = f', {location.address}' if location.address else ''
    return {
        'id': location.location_id,
        'name': location.location_name,
        'address': location.address,
        'verified': coord is not None,
        'lat': coord[0] if coord else None,
        'lng': coord[1] if coord else None,
        'unverified_note': (
            None if coord is not None
            else f'{location.location_name}{suffix} appears in the journey '
                 'instructions, but its map position has not yet been '
                 'verified.'
        ),
    }


def _bounds_and_center(points):
    """[sw, ne] bounds + centre for a list of [lat, lng] points."""
    if not points:
        return None, list(KABANKALAN_CENTER)
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    south, north = min(lats), max(lats)
    west, east = min(lngs), max(lngs)
    if (north - south) < 0.0005 and (east - west) < 0.0005:
        # One (or clustered) markers only - fitBounds would over-zoom.
        return None, [(south + north) / 2, (west + east) / 2]
    bounds = [[south, west], [north, east]]
    center = [(south + north) / 2, (west + east) / 2]
    return bounds, center


def _journey_map_points(origin, destination, legs):
    """Collect the two endpoint markers for a journey's map payload.

    Exactly two pins are drawn - the starting point (green) and the
    destination (red) - plus one continuous ride path. Intermediate stops,
    transfer points and landmarks are deliberately omitted from the payload
    so the map stays clean: only the two endpoints and the route line.
    """
    leg_payloads = []
    all_points = []
    unverified = set()

    def remember(location, name):
        coord = _coord(location)
        if coord is None:
            suffix = (
                f', {location.address}' if getattr(location, 'address', None) else ''
            )
            unverified.add(f'{name}{suffix}')
        else:
            all_points.append(coord)
        return coord

    for leg_index, leg in enumerate(legs):
        leg_payloads.append({
            'leg_index': leg_index,
            'route_id': leg['route_id'],
            'route_code': leg['route'].route_code,
            'route_name': leg['route'].route_name,
            'mode': leg['route'].transport_type.transport_name,
            'color': LEG_COLORS[leg_index % len(LEG_COLORS)],
            'board_at': leg['board_at'],
            'alight_at': leg['alight_at'],
            'minutes': leg['minutes'],
            'distance_km': leg.get('distance_km', 0.0),
            'fare': None if leg['fare'] is None else float(leg['fare']),
            'fare_recorded': leg.get('fare_recorded', True),
            'fare_discount': (
                None if leg.get('fare_discount') is None
                else float(leg['fare_discount'])
            ),
            'discount_fare_recorded': leg.get('discount_fare_recorded', False),
        })

    # The two endpoint pins themselves.
    remember(origin, origin.location_name)
    remember(destination, destination.location_name)

    bounds, center = _bounds_and_center(all_points)
    return {
        'legs': leg_payloads,
        'transfer_points': [],
        'landmarks': [],
        'bounds': bounds,
        'center': center,
        'unverified_names': sorted(unverified),
        'has_markers': bool(all_points),
        'rides': len(legs),
    }


def _build_journey_map(origin, destination, legs, transfers=None,
                       total_time=None, total_distance=None):
    """Full map payload for one journey option."""
    geometry = _journey_map_points(origin, destination, legs)
    return {
        'label': (
            f'{origin.location_name} to {destination.location_name}'
        ),
        'center': {'lat': geometry['center'][0], 'lng': geometry['center'][1]},
        'bounds': geometry['bounds'],
        'origin': _endpoint_dict(origin),
        'destination': _endpoint_dict(destination),
        'journey_available': True,
        'rides': geometry['rides'],
        'total_time': total_time,
        'total_distance_km': total_distance,
        'legs': geometry['legs'],
        'transfer_points': geometry['transfer_points'],
        'landmarks': geometry['landmarks'],
        'unverified_names': geometry['unverified_names'],
        'has_markers': geometry['has_markers'],
        'base_map': 'Google Maps JavaScript API (Leaflet fallback available)',
        'road_path_service': (
            'Google Maps DirectionsService connects the starting point '
            'straight to the destination as one continuous path. If '
            'Directions is unavailable the client falls back to the free '
            'OSRM demo server; the ride path is only ever drawn from real '
            'road geometry - never as a straight line between stops.'
        ),
    }


def locations_map(origin, destination):
    """Map payload for a search that produced no journey.

    Only the two endpoint pins are drawn (starting point and destination),
    with no connecting line - never an invented path.
    """
    geometry = _journey_map_points(
        origin, destination, legs=[],
    )
    return {
        'label': f'{origin.location_name} to {destination.location_name}',
        'center': {'lat': geometry['center'][0], 'lng': geometry['center'][1]},
        'bounds': geometry['bounds'],
        'origin': _endpoint_dict(origin),
        'destination': _endpoint_dict(destination),
        'journey_available': False,
        'rides': 0,
        'total_time': None,
        'total_distance_km': 0,
        'legs': [],
        'transfer_points': [],
        'landmarks': [],
        'unverified_names': geometry['unverified_names'],
        'has_markers': geometry['has_markers'],
        'base_map': 'Google Maps JavaScript API (Leaflet fallback available)',
    }


def _finalize(raw_journey, origin, destination, include_map=True):
    legs = raw_journey['legs']
    transfers = raw_journey.get('transfer_details', [])

    # One blue path per ride; a recorded transfer between two rides keeps
    # each leg in the blue family with its own swatch.
    for leg_index, leg in enumerate(legs):
        leg['color'] = LEG_COLORS[leg_index % len(LEG_COLORS)]
        leg['transfer_after'] = (
            transfers[leg_index] if leg_index < len(transfers) else None
        )

    transfer_fare = sum(
        (t['fare'] for t in transfers if t['fare'] is not None),
        Decimal('0.00'),
    )
    unknown_fare_routes = sorted({
        leg['route'].route_code
        for leg in legs
        if not leg.get('fare_recorded')
    })
    fare_known = not unknown_fare_routes
    if fare_known:
        ride_fare = sum((leg['fare'] for leg in legs), Decimal('0.00'))
        total_fare = ride_fare + transfer_fare
    else:
        ride_fare = None
        total_fare = None

    # Student/PWD price: the per-leg discounted fare records plus any
    # recorded flat transfer extras (a transfer fee is paid by everyone).
    # A route with no discounted record means no trustworthy total, so the
    # presentation layer reports "not recorded" rather than inventing 20%.
    unknown_discount_routes = sorted({
        leg['route'].route_code
        for leg in legs
        if not leg.get('discount_fare_recorded')
    })
    discount_known = not unknown_discount_routes
    if discount_known:
        discount_ride_fare = sum(
            (leg['fare_discount'] for leg in legs), Decimal('0.00'),
        )
        student_fare = discount_ride_fare + transfer_fare
    else:
        discount_ride_fare = None
        student_fare = None

    ride_time = sum(leg['minutes'] for leg in legs)
    transfer_time = sum(t['time'] for t in transfers)
    total_time = ride_time + transfer_time
    total_distance = round(
        sum(leg.get('distance_km', 0.0) for leg in legs), 2,
    )
    transport_names = sorted({
        leg['route'].transport_type.transport_name for leg in legs
    })

    return {
        'legs': legs,
        'transfers': transfers,
        'transfer_count': len(legs) - 1,
        'ride_fare': ride_fare,
        'transfer_fare': transfer_fare,
        'total_fare': total_fare,
        'fare_known': fare_known,
        'unknown_fare_routes': unknown_fare_routes,
        'discount_ride_fare': discount_ride_fare,
        'student_fare': student_fare,
        'discount_known': discount_known,
        'unknown_discount_routes': unknown_discount_routes,
        'ride_time': ride_time,
        'transfer_time': transfer_time,
        'total_time': total_time,
        'total_distance_km': total_distance,
        'transport_names': transport_names,
        'origin': origin,
        'destination': destination,
        'steps': _build_steps(
            origin.location_name, destination.location_name, legs, transfers,
        ),
        'map': (
            _build_journey_map(
                origin, destination, legs, transfers,
                total_time=total_time, total_distance=total_distance,
            )
            if include_map else None
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _transfer_payload(transfer, first_route, second_route):
    """One recorded transfer, shaped for the journey panel and map."""
    location = transfer.transfer_location
    coordinate = _coord(location)
    return {
        'transfer_id': transfer.transfer_id,
        'location_id': transfer.transfer_location_id,
        'location_name': location.location_name,
        'lat': coordinate[0] if coordinate else None,
        'lng': coordinate[1] if coordinate else None,
        'from_code': first_route.route_code,
        'to_code': second_route.route_code,
        'instructions': transfer.transfer_instructions,
        'time': transfer.estimated_transfer_time or 0,
        'fare': transfer.additional_estimated_fare,
        'fare_recorded': True,
    }


def find_journeys(origin_id, destination_id, origin=None, destination=None,
                  network=None, include_map=True):
    """Return recorded ride options supporting a trip between two locations.

    Every journey is built from ``route_stops`` and ``route_transfers``:

    * a direct ride when one route passes both the origin and the destination
      (ridden in either direction of its stop list);
    * a two-ride journey when a recorded transfer connects a route serving
      the origin to a route serving the destination at the recorded transfer
      point.

    No stop, connection or fare is invented. If no recorded route or transfer
    serves the pair, an empty list is returned and the page says so honestly.

    ``network`` may be a context returned by ``_load_network()`` so repeated
    searches reuse the same in-memory indexes. ``include_map=False`` skips
    the heavier map payload when only fare/time summaries are needed.
    """
    if origin is None:
        origin = Location.objects.get(pk=origin_id)
    if destination is None:
        destination = Location.objects.get(pk=destination_id)

    ctx = network if network is not None else _load_network()
    (
        routes, stops_by_route, order_index, fares, student_fares,
        route_distances, _straight_distances, _straight_routes,
        transfers_from,
    ) = ctx

    journeys = []
    seen = set()
    ordered_route_ids = sorted(
        routes, key=lambda route_id: routes[route_id].route_code
    )

    for route_id in ordered_route_ids:
        index = order_index.get(route_id, {})
        if origin_id not in index or destination_id not in index:
            continue
        leg = _make_leg(route_id, origin_id, destination_id, ctx)
        key = (leg['route_id'], leg['board_at'], leg['alight_at'])
        if key in seen:
            continue
        seen.add(key)
        journeys.append(
            _finalize(
                {'legs': [leg], 'transfer_details': []},
                origin, destination, include_map=include_map,
            )
        )

    # One recorded change of vehicle. Each ``route_transfers`` row names the
    # first route, the second route and the place where the commuter alights
    # and boards again; the extra recorded fare is added by ``_finalize``.
    for first_route_id in ordered_route_ids:
        first_index = order_index.get(first_route_id, {})
        if origin_id not in first_index:
            continue
        for transfer in transfers_from.get(first_route_id, ()):
            second_route_id = transfer.to_route_id
            if second_route_id == first_route_id:
                continue
            second_index = order_index.get(second_route_id, {})
            transfer_location_id = transfer.transfer_location_id
            if transfer_location_id not in first_index:
                continue
            if transfer_location_id not in second_index:
                continue
            if destination_id not in second_index:
                continue
            if transfer_location_id in (origin_id, destination_id):
                continue

            first_leg = _make_leg(
                first_route_id, origin_id, transfer_location_id, ctx,
            )
            second_leg = _make_leg(
                second_route_id, transfer_location_id, destination_id, ctx,
            )
            key = (
                first_leg['route_id'], first_leg['board_at'],
                first_leg['alight_at'], second_leg['route_id'],
                second_leg['alight_at'],
            )
            if key in seen:
                continue
            seen.add(key)
            journeys.append(
                _finalize(
                    {
                        'legs': [first_leg, second_leg],
                        'transfer_details': [
                            _transfer_payload(
                                transfer, routes[first_route_id],
                                routes[second_route_id],
                            ),
                        ],
                    },
                    origin, destination, include_map=include_map,
                )
            )

    return journeys


def fastest_travel_minutes(origin_id, destination_id):
    """Return the quickest estimated journey time for a pair, or ``None``."""
    journeys = find_journeys(
        origin_id, destination_id, include_map=False,
    )
    if not journeys:
        return None
    return min(journey['total_time'] for journey in journeys)


def _fare_rank(journey):
    """Sort rank for a journey: known fares first, then unknown ones."""
    fare = journey.get('total_fare')
    if fare is None:
        return (1, Decimal('0.00'))
    return (0, fare)


SORT_KEYS = {
    'fare': lambda j: (
        *_fare_rank(j), j['total_time'], j['transfer_count'],
    ),
    'time': lambda j: (
        j['total_time'], *_fare_rank(j), j['transfer_count'],
    ),
    'transfers': lambda j: (
        j['transfer_count'], *_fare_rank(j), j['total_time'],
    ),
}


def sort_journeys(journeys, sort='fare'):
    """Sort journeys; ties are broken so results stay deterministic."""
    key = SORT_KEYS.get(sort, SORT_KEYS['fare'])
    return sorted(journeys, key=key)


# The three local transport modes Find My Route presents, in display order.
JOURNEY_MODE_DISPLAY = ('Jeepney', 'Bus', 'Tricycle')


def _journey_modes(journey):
    """The set of transport names used by a journey's legs."""
    return {
        leg['route'].transport_type.transport_name for leg in journey['legs']
    }


def select_mode_journeys(journeys, modes=JOURNEY_MODE_DISPLAY):
    """Pick the single best journey for each transport mode.

    ``journeys`` must already be sorted with the commuter's chosen sort, so
    for each mode the first match wins: a journey made only of that mode is
    preferred, otherwise the first journey that includes it. At most one
    journey per mode is returned, in the ``modes`` display order.

    Only modes present in the network can yield a journey, so a pair with no
    bus service shows two cards instead of a padded list. If no journey in
    any of the requested modes exists, the original (still sorted) list is
    returned truncated to the same number of slots, so a reachable pair
    never renders an empty result.
    """
    remaining = list(journeys)
    selected = [None] * len(modes)
    # Pass 1: journeys made only of this mode.
    for index, mode in enumerate(modes):
        pick = next(
            (j for j in remaining if _journey_modes(j) == {mode}),
            None,
        )
        if pick is not None:
            remaining.remove(pick)
            selected[index] = pick
    # Pass 2: mixed-mode journeys that include this mode.
    for index, mode in enumerate(modes):
        if selected[index] is not None:
            continue
        pick = next(
            (j for j in remaining if mode in _journey_modes(j)),
            None,
        )
        if pick is not None:
            remaining.remove(pick)
            selected[index] = pick
    selected = [journey for journey in selected if journey is not None]
    if not selected:
        return list(journeys[:len(modes)])
    return selected


def destination_summaries(origin_id, origin=None):
    """Best fare/time from a starting location to every other active place.

    One entry is returned per active location except the origin, so the
    search form can show a destination's fare and estimated travel time
    before the commuter submits it. ``fare`` and ``minutes`` describe the
    cheapest journey; ``fastest_minutes`` reports the quickest option when
    a different journey is faster.
    """
    if origin is None:
        origin = Location.objects.get(pk=origin_id)

    # Load the active network once and reuse it for every destination search
    # instead of rebuilding the indexes per pair. Barangays, terminals,
    # stops, schools and landmarks are all valid destinations now.
    network = _load_network()
    destinations = (
        Location.objects.filter(status='active')
        .exclude(pk=origin_id)
        .select_related('barangay')
        .order_by('location_type', 'location_name')
    )

    summaries = []
    for destination in destinations:
        journeys = find_journeys(
            origin_id, destination.location_id,
            origin=origin, destination=destination,
            network=network, include_map=False,
        )
        if not journeys:
            summaries.append({
                'location_id': destination.location_id,
                'location_name': destination.location_name,
                'has_route': False,
                'has_fare': False,
                'fare': None,
                'minutes': None,
                'fastest_minutes': None,
                'transfers': None,
            })
            continue

        known_fare_journeys = [
            journey for journey in journeys
            if journey['total_fare'] is not None
        ]
        if known_fare_journeys:
            cheapest = min(known_fare_journeys, key=SORT_KEYS['fare'])
            fare = float(cheapest['total_fare'])
        else:
            # Every ride on the cheapest path has no active fare record; the
            # destination is still reachable, just not priced by the data.
            cheapest = min(journeys, key=SORT_KEYS['time'])
            fare = None
        fastest = min(journeys, key=SORT_KEYS['time'])
        summaries.append({
            'location_id': destination.location_id,
            'location_name': destination.location_name,
            'has_route': True,
            'has_fare': fare is not None,
            'fare': fare,
            'minutes': cheapest['total_time'],
            'fastest_minutes': fastest['total_time'],
            'transfers': cheapest['transfer_count'],
        })

    return summaries


# ---------------------------------------------------------------------------
# Helpers for the search page
# ---------------------------------------------------------------------------
def location_choices():
    """Every active location offered in the From/To comboboxes.

    The original 32 barangays remain available, and terminals, stops,
    schools, markets and landmarks are selectable too because the route
    engine can board/alight at any recorded stop. This is what makes the
    Google Maps journey directions useful for the actual network records.
    """
    return list(
        Location.objects.filter(status='active')
        .select_related('barangay')
        .order_by('location_type', 'location_name')
        .values(
            'location_id', 'location_name', 'location_type', 'address',
            'barangay__barangay_name', 'latitude', 'longitude',
        )
    )


def map_locations():
    """Every recorded location that can be pinned on the Kabankalan map.

    Transport modes and route codes are joined from ``route_stops`` ->
    ``routes`` -> ``transportation_types`` so the Google/Leaflet markers can
    show which jeepney, bus, van or tricycle routes serve each place. All of
    it is database driven; nothing about the markers is hard-coded.
    """
    rows = list(
        Location.objects.filter(status='active')
        .exclude(latitude__isnull=True)
        .exclude(longitude__isnull=True)
        .select_related('barangay')
        .order_by('location_name')
        .values(
            'location_id', 'location_name', 'location_type', 'address',
            'status', 'latitude', 'longitude',
            'barangay__barangay_name',
        )
    )
    by_id = {row['location_id']: row for row in rows}
    for row in rows:
        row['latitude'] = float(row['latitude'])
        row['longitude'] = float(row['longitude'])
        row['transport_types'] = []
        row['route_codes'] = []

    if by_id:
        stop_rows = (
            RouteStop.objects.filter(
                location_id__in=by_id.keys(),
                route__status='active',
            )
            .select_related('route__transport_type')
            .order_by('route__route_code')
        )
        for stop in stop_rows:
            row = by_id.get(stop.location_id)
            if row is None:
                continue
            mode = stop.route.transport_type.transport_name
            if mode not in row['transport_types']:
                row['transport_types'].append(mode)
            code = stop.route.route_code
            if code not in row['route_codes']:
                row['route_codes'].append(code)

    for row in rows:
        row['transport_types'].sort(key=str.lower)
        row['route_codes'].sort()
    return rows


def route_distance_km(stops):
    """Public helper: distance for a list of ``RouteStop`` rows."""
    return _distance_km_for_stops([
        {'location': stop.location} for stop in stops
    ])


def transport_options():
    """Every active route with its mode, fare, distance and endpoints.

    Used by the "Available transportation options" panel on the search page
    so commuters can browse the complete network before searching, and so
    the Google Maps markers and route directions all come from one source.
    """
    routes = (
        Route.objects.filter(status='active')
        .select_related('transport_type', 'origin', 'destination')
        .prefetch_related('stops__location', 'fares__fare_type')
        .order_by('transport_type__transport_name', 'route_code')
    )

    options = []
    for route in routes:
        stops = sorted(route.stops.all(), key=lambda stop: stop.stop_order)
        # One common resolver for the whole network: the newest currently
        # effective active row per (route, fare category) is the amount the
        # commuter sees, exactly as saved by the administrator.
        current = latest_active_fares(route.fares.all())
        regular_fare = current.get((route.route_id, REGULAR_FARE_TYPE_ID))
        student_fare = current.get(
            (route.route_id, DISCOUNT_FARE_TYPE_IDS[0]),
        )
        pwd_fare = current.get(
            (route.route_id, DISCOUNT_FARE_TYPE_IDS[1]),
        )
        discounted = student_fare or pwd_fare

        distance = route_distance_km(stops)
        stop_location_ids = sorted({
            stop.location_id for stop in stops
        } | {route.origin_id, route.destination_id})
        options.append({
            'route_id': route.route_id,
            'route_code': route.route_code,
            'route_name': route.route_name,
            'transport_name': route.transport_type.transport_name,
            'transport_key': route.transport_type.transport_name.lower(),
            'origin_id': route.origin_id,
            'destination_id': route.destination_id,
            'origin_name': route.origin.location_name,
            'destination_name': route.destination.location_name,
            'stop_location_ids': stop_location_ids,
            'boarding_point': (
                stops[0].location.location_name if stops
                else route.origin.location_name
            ),
            'dropoff_point': (
                stops[-1].location.location_name if stops
                else route.destination.location_name
            ),
            'minutes': route.estimated_travel_time,
            'stops_count': len(stops),
            'distance_km': distance,
            'fare': regular_fare.total_estimated_fare if regular_fare else None,
            'student_fare': (
                discounted.total_estimated_fare if discounted else None
            ),
        })
    return options


def popular_destinations(limit=6):
    """Frequently searched barangays, with route-based fallback."""
    result = []
    seen = set()

    rows = (
        SearchHistory.objects.filter(
            destination__location_type=BARANGAY_LOCATION_TYPE,
        ).values('destination_id')
        .annotate(hits=Count('search_id'))
        .order_by('-hits', 'destination_id')[:limit * 2]
    )
    candidates = [row['destination_id'] for row in rows]
    locations = {
        loc.pk: loc
        for loc in Location.objects.filter(
            pk__in=candidates, status='active',
            location_type=BARANGAY_LOCATION_TYPE,
        ).select_related('barangay')
    }
    for row in rows:
        location = locations.get(row['destination_id'])
        if location and location.pk not in seen:
            seen.add(location.pk)
            result.append(location)

    if len(result) < limit:
        destination_ids = Route.objects.filter(
            status='active',
            destination__location_type=BARANGAY_LOCATION_TYPE,
        ).values_list('destination_id', flat=True)
        for location_id in destination_ids:
            if location_id in seen:
                continue
            location = Location.objects.filter(
                pk=location_id, status='active',
                location_type=BARANGAY_LOCATION_TYPE,
            ).select_related('barangay').first()
            if location:
                seen.add(location.pk)
                result.append(location)
            if len(result) >= limit:
                break

    return result[:limit]
