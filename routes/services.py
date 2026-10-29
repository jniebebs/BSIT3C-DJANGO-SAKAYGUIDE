"""Route-search logic for the "Where do you want to go?" feature.

Everything here is computed from records already stored in sakayguide_db
(routes, route_stops, route_transfers, route_fares, route_landmarks,
locations.latitude / locations.longitude). Nothing is invented:

* a journey is only returned when real rows support it;
* map markers are only drawn for locations with verified coordinates
  (locations.latitude / longitude, populated from OpenStreetMap);
* when coordinates are missing the place stays in the journey
  instructions and is reported as "map position not yet verified";
* fares/times are labelled as provisional estimates by the presentation
  layer.
"""
from collections import deque
from decimal import Decimal

from django.db.models import Count

from .models import (
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

# Search depth limits: a journey may use at most MAX_LEGS rides
# (i.e. MAX_LEGS - 1 transfers), and at most MAX_JOURNEYS are returned.
MAX_LEGS = 3
MAX_JOURNEYS = 12

# Distinct, colour-blind friendly line colours, one per ride (up to
# MAX_LEGS); journeys wrap around the palette when more legs exist.
LEG_COLORS = ('#1c7ed6', '#0ca678', '#e8590c')

# Kabankalan City poblacion (OpenStreetMap, October 2026). Used only as
# the "no markers to fit" default view, never to fake coordinates.
KABANKALAN_CENTER = (9.9926, 122.8135)
FALLBACK_ZOOM = 12


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

    order_index = {
        rid: {entry['location_id']: i for i, entry in enumerate(entries)}
        for rid, entries in stops_by_route.items()
    }

    transfers = list(
        RouteTransfer.objects.filter(
            from_route_id__in=routes, to_route_id__in=routes
        ).select_related('transfer_location', 'from_route', 'to_route')
    )

    # Active regular fares; the latest effective_date wins.
    fares = {}
    for f in RouteFare.objects.filter(
        route_id__in=routes,
        fare_type_id=REGULAR_FARE_TYPE_ID,
        status=RouteFare.STATUS_ACTIVE,
    ).order_by('effective_date'):
        fares[f.route_id] = f

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
        routes, stops_by_route, order_index, transfers, fares, landmarks,
        locations_by_id,
    )


# ---------------------------------------------------------------------------
# Journey building
# ---------------------------------------------------------------------------
def _make_leg(route_id, from_location_id, to_location_id, ctx):
    """Build one ride (leg) of a journey between two stops of one route."""
    (routes, stops_by_route, order_index, _, fares, landmarks,
     locations_by_id) = ctx
    index = order_index[route_id]
    i, j = index[from_location_id], index[to_location_id]
    segment = stops_by_route[route_id][i:j + 1]
    start, end = segment[0], segment[-1]

    minutes = end['time'] - start['time']
    if minutes <= 0:
        minutes = routes[route_id].estimated_travel_time

    fare_record = fares.get(route_id)
    segment_locations = {entry['location_id'] for entry in segment}
    leg_landmarks = [
        lm for lm in landmarks.get(route_id, [])
        if lm.location_id in segment_locations
    ]

    return {
        'route': routes[route_id],
        'route_id': route_id,
        'board_at': start['name'],
        'alight_at': end['name'],
        'minutes': minutes,
        'fare': fare_record.total_estimated_fare if fare_record else Decimal('0.00'),
        'fare_record': fare_record,
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


def _transfer_dict(transfer):
    return {
        'location_id': transfer.transfer_location_id,
        'location': transfer.transfer_location,
        'location_name': transfer.transfer_location.location_name,
        'instructions': transfer.transfer_instructions,
        'time': transfer.estimated_transfer_time,
        'fare': transfer.additional_estimated_fare,
        'from_code': transfer.from_route.route_code,
        'from_name': transfer.from_route.route_name,
        'to_code': transfer.to_route.route_code,
        'to_name': transfer.to_route.route_name,
    }


def _build_steps(origin_name, destination_name, legs, transfers):
    """Generate the step-by-step 'Your Journey' instructions."""
    steps = [f'Start at {origin_name}.']
    for i, leg in enumerate(legs):
        route = leg['route']
        mode = route.transport_type.transport_name.lower()
        steps.append(
            f'Board the {mode} {route.route_code} ({route.route_name}) '
            f'at {leg["board_at"]}.'
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


def _journey_map_points(origin, destination, legs, transfers, locations_by_id):
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

    origin_name = origin.location_name
    destination_name = destination.location_name

    for leg_index, leg in enumerate(legs):
        stops = []
        for stop in leg['stops']:
            location = stop['location']
            coord = remember(location, stop['name'])
            if stop['name'] == origin_name:
                role = 'origin'
            elif stop['name'] == destination_name:
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
            'fare': float(leg['fare']),
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
            'fare': float(transfer['fare']),
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


def _build_journey_map(origin, destination, legs, transfers, locations_by_id,
                       total_time=None):
    """Full map payload for one journey option."""
    geometry = _journey_map_points(
        origin, destination, legs, transfers, locations_by_id,
    )
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
        'legs': geometry['legs'],
        'transfer_points': geometry['transfer_points'],
        'landmarks': geometry['landmarks'],
        'unverified_names': geometry['unverified_names'],
        'has_markers': geometry['has_markers'],
        # front end tiles/services note (no API keys involved)
        'base_map': 'Leaflet with OpenStreetMap tiles',
        'road_path_service': (
            'Road path geometry is fetched from the free OSRM demo server '
            '(OpenStreetMap data). When unavailable the stops are shown '
            'with an approximate connection.'
        ),
    }


def locations_map(origin, destination):
    """Map payload for a search that produced no journey.

    The two endpoints still get markers when coordinates are verified so
    the commuter sees where they are - without any fake connecting line.
    """
    geometry = _journey_map_points(
        origin, destination, legs=[], transfers=[], locations_by_id={},
    )
    return {
        'label': f'{origin.location_name} to {destination.location_name}',
        'center': {'lat': geometry['center'][0], 'lng': geometry['center'][1]},
        'bounds': geometry['bounds'],
        'origin': _endpoint_dict(origin),
        'destination': _endpoint_dict(destination),
        'journey_available': False,
        'rides': 0,
        'legs': [],
        'transfer_points': [],
        'landmarks': [],
        'unverified_names': geometry['unverified_names'],
        'has_markers': geometry['has_markers'],
        'base_map': 'Leaflet with OpenStreetMap tiles',
    }


def _finalize(raw_journey, origin, destination, locations_by_id):
    legs = raw_journey['legs']
    # The frontier search can append the transfer that created the current
    # state once more when its turn to complete the journey comes round;
    # keep each transfer record exactly once, in travel order.
    seen_transfers = set()
    unique_details = []
    for transfer in raw_journey['transfer_details']:
        if transfer.transfer_id in seen_transfers:
            continue
        seen_transfers.add(transfer.transfer_id)
        unique_details.append(transfer)
    transfers = [_transfer_dict(t) for t in unique_details]

    # Per-ride line colours, matching static/js/route-map.js palette.
    for leg_index, leg in enumerate(legs):
        leg['color'] = LEG_COLORS[leg_index % len(LEG_COLORS)]

    ride_fare = sum((leg['fare'] for leg in legs), Decimal('0.00'))
    transfer_fare = sum((t['fare'] for t in transfers), Decimal('0.00'))
    total_fare = ride_fare + transfer_fare

    ride_time = sum(leg['minutes'] for leg in legs)
    transfer_time = sum(t['time'] for t in transfers)
    total_time = ride_time + transfer_time

    return {
        'legs': legs,
        'transfers': transfers,
        'transfer_count': len(legs) - 1,
        'ride_fare': ride_fare,
        'transfer_fare': transfer_fare,
        'total_fare': total_fare,
        'ride_time': ride_time,
        'transfer_time': transfer_time,
        'total_time': total_time,
        'origin': origin,
        'destination': destination,
        'steps': _build_steps(
            origin.location_name, destination.location_name, legs, transfers,
        ),
        'map': _build_journey_map(
            origin, destination, legs, transfers, locations_by_id,
            total_time=total_time,
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def find_journeys(origin_id, destination_id, origin=None, destination=None):
    """Return every journey the database supports for this pair.

    Direct rides are found first, then multi-ride journeys are discovered by
    following ``route_transfers`` rows (up to MAX_LEGS rides).
    """
    if origin is None:
        origin = Location.objects.get(pk=origin_id)
    if destination is None:
        destination = Location.objects.get(pk=destination_id)

    ctx = _load_network()
    routes, stops_by_route, order_index, transfers, fares, landmarks, \
        locations_by_id = ctx

    journeys = []
    seen = set()

    def add(raw):
        key = tuple(
            (leg['route_id'], leg['board_at'], leg['alight_at'])
            for leg in raw['legs']
        )
        if key in seen:
            return
        seen.add(key)
        journeys.append(_finalize(raw, origin, destination, locations_by_id))

    # 1) Direct rides: origin appears before destination on the same route.
    for route_id in routes:
        index = order_index.get(route_id, {})
        if (
            origin_id in index
            and destination_id in index
            and index[origin_id] < index[destination_id]
        ):
            add({
                'legs': [_make_leg(route_id, origin_id, destination_id, ctx)],
                'transfer_details': [],
            })

    # 2) Multi-ride journeys through valid transfer connections.
    queue = deque()
    for route_id in routes:
        index = order_index.get(route_id, {})
        if origin_id not in index:
            continue
        for transfer in transfers:
            if transfer.from_route_id != route_id:
                continue
            stop_location = transfer.transfer_location_id
            if stop_location == origin_id:
                continue
            if stop_location not in index:
                continue
            if index[stop_location] <= index[origin_id]:
                continue
            leg = _make_leg(route_id, origin_id, stop_location, ctx)
            queue.append((stop_location, route_id, [leg], [transfer]))

    visited = set()
    while queue and len(journeys) < MAX_JOURNEYS:
        current_location, route_id, legs, used_transfers = queue.popleft()
        state = (
            current_location,
            route_id,
            tuple(
                (leg['route_id'], leg['board_at'], leg['alight_at'])
                for leg in legs
            ),
        )
        if state in visited:
            continue
        visited.add(state)
        if len(legs) >= MAX_LEGS:
            continue

        for transfer in transfers:
            if transfer.from_route_id != route_id:
                continue
            if transfer.transfer_location_id != current_location:
                continue

            next_route_id = transfer.to_route_id
            next_index = order_index.get(next_route_id, {})
            if current_location not in next_index:
                continue

            # Can the next ride reach the destination directly?
            if (
                destination_id in next_index
                and next_index[destination_id] > next_index[current_location]
            ):
                leg = _make_leg(
                    next_route_id, current_location, destination_id, ctx
                )
                add({
                    'legs': legs + [leg],
                    'transfer_details': used_transfers + [transfer],
                })

            # Or continue to yet another transfer point (multi-transfer trip)?
            if len(legs) + 1 >= MAX_LEGS:
                continue
            for next_transfer in transfers:
                if next_transfer.from_route_id != next_route_id:
                    continue
                next_location = next_transfer.transfer_location_id
                if next_location == current_location:
                    continue
                if next_location not in next_index:
                    continue
                if next_index[next_location] <= next_index[current_location]:
                    continue
                leg = _make_leg(
                    next_route_id, current_location, next_location, ctx
                )
                queue.append((
                    next_location,
                    next_route_id,
                    legs + [leg],
                    used_transfers + [transfer],
                ))

    return journeys


def fastest_travel_minutes(origin_id, destination_id):
    """Return the quickest estimated journey time for a pair, or ``None``."""
    journeys = find_journeys(origin_id, destination_id)
    if not journeys:
        return None
    return min(journey['total_time'] for journey in journeys)


SORT_KEYS = {
    'fare': lambda j: (j['total_fare'], j['total_time'], j['transfer_count']),
    'time': lambda j: (j['total_time'], j['total_fare'], j['transfer_count']),
    'transfers': lambda j: (
        j['transfer_count'], j['total_fare'], j['total_time'],
    ),
}


def sort_journeys(journeys, sort='fare'):
    """Sort journeys; ties are broken so results stay deterministic."""
    key = SORT_KEYS.get(sort, SORT_KEYS['fare'])
    return sorted(journeys, key=key)


# ---------------------------------------------------------------------------
# Helpers for the search page
# ---------------------------------------------------------------------------
def location_choices():
    """All active locations for the From/To dropdowns."""
    return list(
        Location.objects.filter(status='active')
        .select_related('barangay')
        .order_by('location_name')
        .values(
            'location_id', 'location_name', 'location_type', 'address',
            'barangay__barangay_name',
        )
    )


def map_locations():
    """Every recorded location that can be pinned on the Kabankalan map."""
    rows = list(
        Location.objects.exclude(latitude__isnull=True)
        .exclude(longitude__isnull=True)
        .select_related('barangay')
        .order_by('location_name')
        .values(
            'location_id', 'location_name', 'location_type', 'address',
            'status', 'latitude', 'longitude',
            'barangay__barangay_name',
        )
    )
    for row in rows:
        row['latitude'] = float(row['latitude'])
        row['longitude'] = float(row['longitude'])
    return rows


def popular_destinations(limit=6):
    """Frequently searched destinations, with route-based fallback."""
    result = []
    seen = set()

    rows = (
        SearchHistory.objects.values('destination_id')
        .annotate(hits=Count('search_id'))
        .order_by('-hits', 'destination_id')[:limit * 2]
    )
    candidates = [row['destination_id'] for row in rows]
    locations = {
        loc.pk: loc
        for loc in Location.objects.filter(
            pk__in=candidates, status='active'
        ).select_related('barangay')
    }
    for row in rows:
        location = locations.get(row['destination_id'])
        if location and location.pk not in seen:
            seen.add(location.pk)
            result.append(location)

    if len(result) < limit:
        destination_ids = Route.objects.filter(status='active').values_list(
            'destination_id', flat=True
        )
        for location_id in destination_ids:
            if location_id in seen:
                continue
            location = Location.objects.filter(
                pk=location_id, status='active'
            ).select_related('barangay').first()
            if location:
                seen.add(location.pk)
                result.append(location)
            if len(result) >= limit:
                break

    return result[:limit]
