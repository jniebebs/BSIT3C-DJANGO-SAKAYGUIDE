"""Route-search logic for the "Where do you want to go?" feature.

Everything here is computed from records already stored in sakayguide_db
(routes, route_stops, route_transfers, route_fares, route_landmarks,
locations.latitude / locations.longitude). Nothing is invented:

* a journey is only returned when real rows support it: recorded routes can
  be ridden in either direction, and rides change at any stop the two routes
  share (a ``route_transfers`` row supplies the exact instruction, waiting
  time and extra fare when its route pair matches);
* when a route has no ``route_stops`` rows its recorded origin and destination
  are used as the two endpoint stops - the route record itself asserts those
  places are served;
* map markers are only drawn for locations with verified coordinates
  (locations.latitude / longitude, populated from OpenStreetMap);
* when coordinates are missing the place stays in the journey
  instructions and is reported as "map position not yet verified";
* fares and times are labelled as provisional estimates by the presentation
  layer, and a leg whose route has no active regular fare record is reported
  as "fare not recorded" rather than being given a guessed amount.
"""
from collections import deque
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from django.db.models import Count

from .models import (
    BARANGAY_LOCATION_TYPE,
    Location,
    Route,
    RouteFare,
    RouteLandmark,
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

# Search depth limits: a journey may use at most MAX_LEGS rides
# (i.e. MAX_LEGS - 1 transfers). The search keeps up to MAX_JOURNEYS distinct
# route combinations for one origin/destination pair - direct rides first,
# then one- and two-transfer journeys - so the commuter sees the real
# alternatives including different transport combinations.
MAX_LEGS = 3
MAX_JOURNEYS = 24
# Safety bound on the breadth-first expansion so a large network can never
# make one search hang; the current Kabankalan network uses a tiny fraction.
MAX_SEARCH_STATES = 6000

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

    transfers = list(
        RouteTransfer.objects.filter(
            from_route_id__in=routes, to_route_id__in=routes
        ).select_related('transfer_location', 'from_route', 'to_route')
    )

    # Indexes used by the bidirectional journey search.
    #
    # A recorded route may be ridden in either direction: jeepneys, buses,
    # vans and tricycles all make the return trip even when the database only
    # stores one ordered list of stops. ``routes_at_location`` answers
    # "which routes can I board here?". Rides may change at any stop the two
    # routes share; a ``route_transfers`` row only supplies the recorded
    # instruction, waiting time and extra fare for an exact route pair.
    routes_at_location = {}
    for route_id, entries in stops_by_route.items():
        for entry in entries:
            routes_at_location.setdefault(entry['location_id'], set()).add(
                route_id
            )

    transfer_hints = {
        (
            transfer.from_route_id,
            transfer.transfer_location_id,
            transfer.to_route_id,
        ): transfer
        for transfer in transfers
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

    landmarks = {}
    for lm in RouteLandmark.objects.filter(route_id__in=routes).select_related(
        'location'
    ).order_by('route_id', 'display_order'):
        landmarks.setdefault(lm.route_id, []).append(lm)

    # Every active location keyed by id, so map payloads can resolve the
    # verified coordinates of any stop/transfer/landmark.
    locations_by_id = {
        loc.location_id: loc
        for loc in Location.objects.filter(status='active')
    }

    return (
        routes, stops_by_route, order_index, transfers, fares, student_fares,
        landmarks, locations_by_id, routes_at_location, transfer_hints,
    )


# ---------------------------------------------------------------------------
# Journey building
# ---------------------------------------------------------------------------
def _make_leg(route_id, from_location_id, to_location_id, ctx):
    """Build one ride (leg) of a journey between two stops of one route.

    The recorded stop list can be travelled in either direction, so the
    segment is reversed when the destination comes before the origin on the
    stored route. ``minutes`` is the absolute difference of the recorded
    cumulative stop times, which stays correct for the return trip.
    """
    (routes, stops_by_route, order_index, _, fares, student_fares, landmarks,
     locations_by_id, _, _) = ctx
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
    segment_locations = {entry['location_id'] for entry in segment}
    leg_landmarks = [
        lm for lm in landmarks.get(route_id, [])
        if lm.location_id in segment_locations
    ]
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
        'stops': [
            {
                'location': entry['location'],
                'location_id': entry['location_id'],
                'name': entry['name'],
                'order': entry['order'],
                'time': entry['time'],
                'is_transfer': entry['is_transfer'],
            }
            for entry in segment
        ],
        'landmarks': [
            {
                'location': locations_by_id.get(lm.location_id)
                            or lm.location,
                'name': lm.location.location_name,
                'description': lm.landmark_description,
                'distance': lm.distance_from_origin,
            }
            for lm in leg_landmarks
        ],
    }


def _transfer_dict(transfer, from_route=None, to_route=None,
                   location=None, next_alight=None):
    """Describe a transfer.

    When a recorded ``route_transfers`` row matches the route pair and the
    location, its instruction, waiting time and additional fare are used.
    Otherwise a plain, factual instruction is built from the two routes -
    no fare or waiting time is invented.
    """
    if transfer is not None:
        return {
            'location_id': transfer.transfer_location_id,
            'location': transfer.transfer_location,
            'location_name': transfer.transfer_location.location_name,
            'instructions': transfer.transfer_instructions,
            'time': transfer.estimated_transfer_time,
            'fare': transfer.additional_estimated_fare,
            'fare_recorded': True,
            'from_code': from_route.route_code,
            'from_name': from_route.route_name,
            'to_code': to_route.route_code,
            'to_name': to_route.route_name,
            'recorded': True,
        }

    mode = to_route.transport_type.transport_name.lower()
    target = f' towards {next_alight}' if next_alight else ''
    return {
        'location_id': location.location_id,
        'location': location,
        'location_name': location.location_name,
        'instructions': (
            f'Alight at {location.location_name}. Board the {mode} '
            f'{to_route.route_code} ({to_route.route_name}){target}.'
        ),
        'time': 0,
        # No route_transfers row exists for this route pair, so any extra
        # fee or waiting time is simply unknown - not zero, not guessed.
        'fare': None,
        'fare_recorded': False,
        'from_code': from_route.route_code,
        'from_name': from_route.route_name,
        'to_code': to_route.route_code,
        'to_name': to_route.route_name,
        'recorded': False,
    }


def _build_steps(origin_name, destination_name, legs, transfers):
    """Generate the step-by-step 'Your Journey' instructions."""
    steps = [f'Start at {origin_name}.']
    for i, leg in enumerate(legs):
        route = leg['route']
        mode = route.transport_type.transport_name.lower()
        steps.append(
            f'Board the {mode} {route.route_code} ({route.route_name}) '
            f'at {leg["board_at"]} towards {leg["alight_at"]}.'
        )
        intermediate = [s['name'] for s in leg['stops'][1:-1]]
        if intermediate:
            steps.append('Follow the stops and landmarks: ' + ', '.join(intermediate) + '.')
        if i < len(transfers):
            transfer = transfers[i]
            extra = (
                f' Pay an additional fare of PHP {transfer["fare"]}.'
                if transfer['fare'] else ''
            )
            wait = (
                f' Allow about {transfer["time"]} minutes to transfer.'
                if transfer['time'] else ''
            )
            steps.append(
                f'Get off at {transfer["location_name"]}. '
                f'{transfer["instructions"]}{extra}{wait}'
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


def _journey_map_points(origin, destination, legs, transfers):
    """Collect map points and unverified names for one journey."""
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
        stops = []
        for stop in leg['stops']:
            location = stop['location']
            coord = remember(location, stop['name'])
            if stop['location_id'] == origin.location_id:
                role = 'origin'
            elif stop['location_id'] == destination.location_id:
                role = 'destination'
            else:
                role = 'intermediate'
            stops.append({
                'location_id': stop['location_id'],
                'name': stop['name'],
                'order': stop['order'],
                'time': stop['time'],
                'is_transfer': stop['is_transfer'],
                'role': role,
                'lat': coord[0] if coord else None,
                'lng': coord[1] if coord else None,
            })
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
            'stops': stops,
        })

    transfer_points = []
    for transfer in transfers:
        location = transfer.get('location')
        coord = remember(location, transfer['location_name'])
        transfer_points.append({
            'location_id': transfer['location_id'],
            'name': transfer['location_name'],
            'lat': coord[0] if coord else None,
            'lng': coord[1] if coord else None,
            'instructions': transfer['instructions'],
            'time': transfer['time'],
            'fare': None if transfer['fare'] is None else float(transfer['fare']),
            'fare_recorded': transfer.get('fare_recorded', False),
            'from_code': transfer['from_code'],
            'to_code': transfer['to_code'],
        })

    landmark_points = []
    for leg_index, leg in enumerate(legs):
        route_code = leg['route'].route_code
        for landmark in leg['landmarks']:
            location = landmark.get('location')
            coord = remember(location, landmark['name'])
            landmark_points.append({
                'location_id': getattr(location, 'location_id', None),
                'name': landmark['name'],
                'description': landmark['description'],
                'distance': float(landmark['distance'] or 0),
                'route_code': route_code,
                'leg_index': leg_index,
                'lat': coord[0] if coord else None,
                'lng': coord[1] if coord else None,
            })

    # The searched endpoints themselves (may not sit on any route).
    remember(origin, origin.location_name)
    remember(destination, destination.location_name)

    bounds, center = _bounds_and_center(all_points)
    return {
        'legs': leg_payloads,
        'transfer_points': transfer_points,
        'landmarks': landmark_points,
        'bounds': bounds,
        'center': center,
        'unverified_names': sorted(unverified),
        'has_markers': bool(all_points),
        'rides': len(legs),
    }


def _build_journey_map(origin, destination, legs, transfers,
                       total_time=None, total_distance=None):
    """Full map payload for one journey option."""
    geometry = _journey_map_points(origin, destination, legs, transfers)
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
            'Google Maps DirectionsService follows the recorded stops as '
            'waypoints. If Directions is unavailable the client falls back '
            'to the free OSRM demo server; the ride path is only ever drawn '
            'from real road geometry - never as a straight line between '
            'stops.'
        ),
    }


def locations_map(origin, destination):
    """Map payload for a search that produced no journey.

    The two endpoints still get markers when coordinates are verified so
    the commuter sees where they are - without any fake connecting line.
    """
    geometry = _journey_map_points(
        origin, destination, legs=[], transfers=[],
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
    # One transfer descriptor per ride change, in travel order; the search
    # emits exactly one per leg boundary.
    transfers = raw_journey['transfer_details']

    # Per-ride line colours (blue shades), matching static/js/route-map.js.
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
        # Recorded extra transfer fares are still real even when a ride's
        # base fare is unknown; the journey total stays unavailable.
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
    """Return the journeys the database supports for this pair.

    Direct rides are found first, then multi-ride journeys are discovered by
    riding the recorded routes in either direction and changing at any stop
    the two routes share (up to MAX_LEGS rides and MAX_JOURNEYS options). A
    ``route_transfers`` row supplies the exact instruction, waiting time and
    extra fare when its route pair matches; otherwise a factual
    board-the-next-route instruction is generated without inventing a fee or
    waiting time.

    ``network`` may be a context returned by ``_load_network()`` so repeated
    searches reuse the same in-memory indexes. ``include_map=False`` skips
    the heavier map payload when only fare/time summaries are needed.
    """
    if origin is None:
        origin = Location.objects.get(pk=origin_id)
    if destination is None:
        destination = Location.objects.get(pk=destination_id)

    ctx = network if network is not None else _load_network()
    (routes, stops_by_route, order_index, _, fares, student_fares, landmarks,
     locations_by_id, routes_at_location, transfer_hints) = ctx

    journeys = []
    seen = set()
    ordered_route_ids = sorted(
        routes, key=lambda route_id: routes[route_id].route_code
    )

    def add(raw):
        key = tuple(
            (leg['route_id'], leg['board_at'], leg['alight_at'])
            for leg in raw['legs']
        )
        if key in seen:
            return False
        seen.add(key)
        journeys.append(
            _finalize(raw, origin, destination, include_map=include_map)
        )
        return True

    def location_obj(location_id, fallback):
        return locations_by_id.get(location_id) or fallback

    def transfer_for(from_leg, next_route_id, location_id, current_obj,
                     next_leg):
        """Recorded transfer details for this exact route pair, if usable.

        Reverse rides get a direction-aware generated instruction instead,
        because a recorded note that says "board the jeepney to Bantayan"
        would be wrong when travelling the other way.
        """
        hint = transfer_hints.get(
            (from_leg['route_id'], location_id, next_route_id)
        )
        if hint is not None and (
            from_leg.get('forward', True) and next_leg.get('forward', True)
        ):
            transfer = hint
        else:
            transfer = None
        return _transfer_dict(
            transfer,
            routes[from_leg['route_id']],
            routes[next_route_id],
            current_obj,
            next_leg['alight_at'],
        )

    # 1) Direct rides: both endpoints appear on the same route, in either
    #    direction of the recorded stop list.
    for route_id in ordered_route_ids:
        index = order_index.get(route_id, {})
        if origin_id in index and destination_id in index:
            add({
                'legs': [_make_leg(route_id, origin_id, destination_id, ctx)],
                'transfer_details': [],
            })

    # 2) Multi-ride journeys. A commuter may change rides at any stop the
    #    two routes share; the recorded transfer row (when one exists) only
    #    enriches that change with its instruction, waiting time and extra
    #    fare.
    queue = deque()
    for route_id in ordered_route_ids:
        index = order_index.get(route_id, {})
        if origin_id not in index:
            continue
        for entry in stops_by_route[route_id]:
            stop_location = entry['location_id']
            if stop_location in (origin_id, destination_id):
                continue
            if not (routes_at_location.get(stop_location, set()) - {route_id}):
                continue
            leg = _make_leg(route_id, origin_id, stop_location, ctx)
            queue.append((
                stop_location,
                [leg],
                [],
                {route_id},
                entry['location'],
            ))

    visited = set()
    expanded = 0
    while queue and len(journeys) < MAX_JOURNEYS:
        if expanded >= MAX_SEARCH_STATES:
            break
        expanded += 1
        current_location, legs, transfer_details, used_routes, current_obj = (
            queue.popleft()
        )
        route_sequence = tuple(
            (leg['route_id'], leg['board_at'], leg['alight_at'])
            for leg in legs
        )
        state = (current_location, frozenset(used_routes), route_sequence)
        if state in visited:
            continue
        visited.add(state)
        if len(legs) >= MAX_LEGS:
            continue

        # Never send the commuter back through a place the journey has
        # already passed; that only produces useless round trips.
        visited_locations = {origin_id}
        for leg in legs:
            visited_locations.update(
                stop['location_id'] for stop in leg['stops']
            )

        from_leg = legs[-1]
        current_obj = location_obj(current_location, current_obj)

        next_route_ids = sorted(
            routes_at_location.get(current_location, set()) - used_routes,
            key=lambda next_route_id: routes[next_route_id].route_code,
        )
        for next_route_id in next_route_ids:
            next_index = order_index.get(next_route_id, {})
            if current_location not in next_index:
                continue

            # Can the next ride reach the destination directly?
            if (
                destination_id in next_index
                and destination_id not in visited_locations
            ):
                next_leg = _make_leg(
                    next_route_id, current_location, destination_id, ctx,
                )
                add({
                    'legs': legs + [next_leg],
                    'transfer_details': transfer_details + [
                        transfer_for(
                            from_leg, next_route_id, current_location,
                            current_obj, next_leg,
                        ),
                    ],
                })

            # Or continue to yet another change point (multi-transfer
            # trip)?
            if len(legs) + 1 >= MAX_LEGS:
                continue
            for entry in stops_by_route[next_route_id]:
                next_location = entry['location_id']
                if next_location in (current_location, destination_id):
                    continue
                if next_location in visited_locations:
                    continue
                if not (
                    routes_at_location.get(next_location, set())
                    - used_routes - {next_route_id}
                ):
                    continue
                next_leg = _make_leg(
                    next_route_id, current_location, next_location, ctx,
                )
                queue.append((
                    next_location,
                    legs + [next_leg],
                    transfer_details + [
                        transfer_for(
                            from_leg, next_route_id, current_location,
                            current_obj, next_leg,
                        ),
                    ],
                    used_routes | {next_route_id},
                    entry['location'],
                ))

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
