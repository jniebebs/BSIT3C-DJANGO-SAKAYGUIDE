"""Route-search logic for the "Where do you want to go?" feature.

Everything here is computed from records already stored in sakayguide_db
(routes, route_stops, route_transfers, route_fares, route_landmarks). Nothing
is invented: a journey is only returned when real rows support it, and all
fares/times are labelled as provisional estimates by the presentation layer.
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

# Maps only ever show Kabankalan City, so no per-location coordinates are
# needed: the front end opens every map on the city itself.
KABANKALAN_CENTER = (10.2435, 122.8183)


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

    return routes, stops_by_route, order_index, transfers, fares, landmarks


# ---------------------------------------------------------------------------
# Journey building
# ---------------------------------------------------------------------------
def _make_leg(route_id, from_location_id, to_location_id, ctx):
    """Build one ride (leg) of a journey between two stops of one route."""
    routes, stops_by_route, order_index, _, fares, landmarks = ctx
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


def _build_map(origin, destination):
    """Build the JSON payload for a search's map.

    The map itself only ever shows Kabankalan City, so the payload just
    carries the searched pair as a label for the front end.
    """
    return {
        'label': f'{origin.location_name} to {destination.location_name}',
        'center': {'lat': KABANKALAN_CENTER[0], 'lng': KABANKALAN_CENTER[1]},
    }


def locations_map(origin, destination):
    """Map payload for a search with no journey."""
    return _build_map(origin, destination)


def _finalize(raw_journey, origin, destination):
    legs = raw_journey['legs']
    transfers = [_transfer_dict(t) for t in raw_journey['transfer_details']]

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
        'map': _build_map(origin, destination),
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
    routes, stops_by_route, order_index, transfers, fares, landmarks = ctx

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
        journeys.append(_finalize(raw, origin, destination))

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
    """All active locations for the From/To dropdowns (the map itself only
    shows Kabankalan City, so no coordinates are attached)."""
    return list(
        Location.objects.filter(status='active')
        .select_related('barangay')
        .order_by('location_name')
        .values(
            'location_id', 'location_name', 'location_type', 'address',
            'barangay__barangay_name',
        )
    )


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
