"""Route-search logic for the "Where do you want to go?" feature.

Everything here is computed from records already stored in sakayguide_db
(routes, route_stops, route_fares, locations.latitude / locations.longitude).
Nothing is invented:

* only direct, single-ride journeys are returned: a route can be ridden in
  either direction, and a journey exists when the route passes both the
  origin and the destination - ridden by one vehicle, with no transfer or
  change of vehicle ever required;
* the map payload carries exactly two pins - the starting point (green) and
  the destination (red) - plus the route's road geometry as one continuous
  blue path; no intermediate stop, transfer point or landmark markers are
  drawn;
* when a route has no ``route_stops`` rows its recorded origin and destination
  are used as the two endpoint stops - the route record itself asserts those
  places are served;
* when coordinates are missing for an endpoint the place stays in the
  journey instructions and is reported as "map position not yet verified";
* fares and times are labelled as provisional estimates by the presentation
  layer, and a leg whose route has no active regular fare record is reported
  as "fare not recorded" rather than being given a guessed amount.
"""
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from django.db.models import Count

from .models import (
    BARANGAY_LOCATION_TYPE,
    Location,
    Route,
    RouteFare,
    RouteStop,
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

# Find My Route presents direct rides only - one continuous ride, no
# transfer or change of vehicle - so every journey is a single leg. The
# number of direct rides between one pair is small (a handful of routes can
# serve the same pair); no artificial cap is applied.

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

    # Active regular fares; the latest effective_date wins.
    fares = {}
    for f in RouteFare.objects.filter(
        route_id__in=routes,
        fare_type_id=REGULAR_FARE_TYPE_ID,
        status=RouteFare.STATUS_ACTIVE,
    ).order_by('effective_date'):
        fares[f.route_id] = f

    # Discounted (Student/PWD) fares per route; latest effective_date wins.
    # Student (2) is preferred when a route carries both discounted records;
    # PWD (4) is used as a fallback. A route with no discounted record is
    # reported as "not recorded" - never given a computed guess.
    student_fares = {}
    for fare_type_id in DISCOUNT_FARE_TYPE_IDS:
        latest = {}
        for f in RouteFare.objects.filter(
            route_id__in=routes,
            fare_type_id=fare_type_id,
            status=RouteFare.STATUS_ACTIVE,
        ).order_by('effective_date'):
            latest[f.route_id] = f
        for route_id, fare in latest.items():
            student_fares.setdefault(route_id, fare)

    return (
        routes, stops_by_route, order_index, fares, student_fares,
    )


# ---------------------------------------------------------------------------
# Journey building
# ---------------------------------------------------------------------------
def _make_leg(route_id, from_location_id, to_location_id, ctx):
    """Build one ride (leg) of a journey between two stops of one route.

    The recorded stop list can be travelled in either direction, so the
    segment is reversed when the destination comes before the origin on the
    stored route. ``minutes`` is the absolute difference of the recorded
    cumulative stop times, which stays correct for the return trip. The
    intermediate stops are deliberately *not* copied into the journey
    payload: the commuter only sees the starting point, the destination and
    one continuous ride.
    """
    (routes, stops_by_route, order_index, fares, student_fares) = ctx
    index = order_index[route_id]
    i, j = index[from_location_id], index[to_location_id]
    forward = i <= j
    if forward:
        segment = stops_by_route[route_id][i:j + 1]
    else:
        segment = list(reversed(stops_by_route[route_id][j:i + 1]))
    start, end = segment[0], segment[-1]

    minutes = abs(end['time'] - start['time'])
    if minutes <= 0:
        minutes = routes[route_id].estimated_travel_time

    fare_record = fares.get(route_id)
    # A route without an active regular fare record must never be shown with
    # a guessed amount; the presentation layer reports "fare not recorded".
    fare = fare_record.total_estimated_fare if fare_record else None
    discount_fare_record = student_fares.get(route_id)
    discount_fare = (
        discount_fare_record.total_estimated_fare
        if discount_fare_record else None
    )
    distance_km = _distance_km_for_stops(segment)

    return {
        'route': routes[route_id],
        'route_id': route_id,
        'board_at': start['name'],
        'alight_at': end['name'],
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

    Every journey is a single direct ride, so the instructions are always
    short: board, ride, alight. No stops, no transfers, no vehicle change.
    """
    steps = [f'Start at {origin_name}.']
    for leg in legs:
        route = leg['route']
        mode = route.transport_type.transport_name.lower()
        steps.append(
            f'Board the {mode} {route.route_code} ({route.route_name}) '
            f'at {leg["board_at"]}.'
        )
        steps.append(
            f'Ride directly to {leg["alight_at"]} — no transfer needed.'
        )
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

    # Single continuous ride: one blue line.
    for leg_index, leg in enumerate(legs):
        leg['color'] = LEG_COLORS[leg_index % len(LEG_COLORS)]

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
def find_journeys(origin_id, destination_id, origin=None, destination=None,
                  network=None, include_map=True):
    """Return the direct rides supporting a trip between two locations.

    Find My Route only offers single, continuous rides: a journey is
    returned when a recorded route passes both the origin and the
    destination, ridden in either direction of its stop list. No transfer
    or change of vehicle is ever required. If no recorded route serves the
    pair, an empty list is returned and the page says so honestly.

    ``network`` may be a context returned by ``_load_network()`` so repeated
    searches reuse the same in-memory indexes. ``include_map=False`` skips
    the heavier map payload when only fare/time summaries are needed.
    """
    if origin is None:
        origin = Location.objects.get(pk=origin_id)
    if destination is None:
        destination = Location.objects.get(pk=destination_id)

    ctx = network if network is not None else _load_network()
    (routes, stops_by_route, order_index, fares, student_fares) = ctx

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
        regular_fare = None
        student_fare = None
        pwd_fare = None
        for fare in sorted(
            (f for f in route.fares.all()
             if f.status == RouteFare.STATUS_ACTIVE),
            key=lambda fare: fare.effective_date,
        ):
            if fare.fare_type_id == REGULAR_FARE_TYPE_ID:
                regular_fare = fare
            elif fare.fare_type_id == DISCOUNT_FARE_TYPE_IDS[0]:
                student_fare = fare
            elif fare.fare_type_id == DISCOUNT_FARE_TYPE_IDS[1]:
                pwd_fare = fare
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
