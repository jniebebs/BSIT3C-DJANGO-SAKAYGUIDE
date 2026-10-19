"""Multi-modal journey planner.

Builds a graph out of route stops and runs Dijkstra over ``(terminal, route)``
states so that switching lines is charged a transfer penalty. Fares are
accumulated per leg: flag-down base fare at boarding plus the per-kilometre
rate for the distance actually ridden.
"""
import heapq
from decimal import Decimal

from .models import Route, Terminal, money
from .serializers import route_json, transport_mode_json

# Minutes lost switching lines (walking + waiting).
TRANSFER_PENALTY_MINUTES = Decimal('5.00')
# Weight applied to fares when the rider asks for the cheapest journey
# (minutes "spent" per peso saved, keeps time and money comparable).
FARE_WEIGHT_MINUTES_PER_PESO = Decimal('2.00')
DEFAULT_MAX_TRANSFERS = 4
OPTIMIZE_CHOICES = ('fastest', 'cheapest')


def build_graph():
    """Return adjacency structures for every active route stop sequence."""
    routes = {}
    serving = {}
    edges = {}

    active_routes = (
        Route.objects.filter(is_active=True)
        .select_related('transport_mode', 'origin_terminal', 'destination_terminal')
        .prefetch_related('stops__terminal')
    )

    for route in active_routes:
        stops = sorted(route.stops.all(), key=lambda s: s.sequence)
        if len(stops) < 2:
            continue

        routes[route.id] = route

        for stop in stops:
            serving.setdefault(stop.terminal_id, set()).add(route.id)
            edges.setdefault(stop.terminal_id, [])

        for index in range(len(stops) - 1):
            current = stops[index]
            following = stops[index + 1]
            segment_time = route.time_between_minutes(index, index + 1, stops)
            segment_distance = following.distance_from_origin_km - current.distance_from_origin_km

            edges[current.terminal_id].append(
                (route.id, following.terminal_id, segment_time, segment_distance)
            )
            if route.bidirectional:
                edges[following.terminal_id].append(
                    (route.id, current.terminal_id, segment_time, segment_distance)
                )

    return {'routes': routes, 'serving': serving, 'edges': edges}


def _leg_payload(route, board_id, stops, distance, leg_time):
    """Serialise one journey leg (a continuous ride on a single route)."""
    alight_id = stops[-1]
    terminal_names = dict(
        Terminal.objects.filter(pk__in=stops).values_list('pk', 'name')
    )
    return {
        'route': route_json(route),
        'mode': transport_mode_json(route.transport_mode),
        'board_terminal_id': board_id,
        'alight_terminal_id': alight_id,
        'stops': [
            {'id': stop_id, 'name': terminal_names.get(stop_id, f'Terminal #{stop_id}')}
            for stop_id in stops
        ],
        'stop_count': max(len(stops) - 1, 0),
        'distance_km': float(money(distance)),
        'fare': float(money(route.base_fare + route.fare_per_km * distance)),
        'time_minutes': float(money(leg_time)),
    }


def _build_steps(journey):
    """Human readable turn-by-turn style steps for offline navigation."""
    steps = []
    legs = journey['legs']
    for index, leg in enumerate(legs):
        board = leg['stops'][0]['name'] if leg['stops'] else ''
        alight = leg['stops'][-1]['name'] if leg['stops'] else ''
        mode = leg['mode']['name']
        if index > 0:
            steps.append({
                'type': 'transfer',
                'terminal': board,
                'text': f'Transfer at {board} to {leg["route"]["name"]} ({mode}).',
            })
        steps.append({
            'type': 'board',
            'terminal': board,
            'text': f'Board {leg["route"]["name"]} ({mode}) at {board}.',
        })
        steps.append({
            'type': 'ride',
            'terminal': alight,
            'text': f'Ride for {leg["stop_count"]} stop(s), about {leg["time_minutes"]} min.',
        })
        steps.append({
            'type': 'alight',
            'terminal': alight,
            'text': f'Alight at {alight} ({leg["route"]["code"]}).',
        })
    if not steps:
        steps.append({'type': 'info', 'terminal': None, 'text': 'You are already at your destination.'})
    return steps


def plan_journey(origin_id, destination_id, optimize='fastest', max_transfers=DEFAULT_MAX_TRANSFERS):
    """Find a multi-leg journey between two terminals.

    Returns a dict with ``found``, totals, legs and navigation steps.
    """
    optimize = optimize if optimize in OPTIMIZE_CHOICES else 'fastest'
    graph = build_graph()

    if origin_id not in graph['serving'] and origin_id != destination_id:
        # Origin exists but has no routes (or does not exist at all).
        return {'found': False, 'reason': 'origin_unreachable'}
    if destination_id not in graph['serving'] and origin_id != destination_id:
        return {'found': False, 'reason': 'destination_unreachable'}

    if origin_id == destination_id:
        return {
            'found': True,
            'optimize': optimize,
            'origin_id': origin_id,
            'destination_id': destination_id,
            'legs': [],
            'steps': _build_steps({'legs': []}),
            'transfers': 0,
            'total_time_minutes': 0.0,
            'transfer_time_minutes': 0.0,
            'total_fare': 0.0,
            'total_distance_km': 0.0,
        }

    fare_weight = FARE_WEIGHT_MINUTES_PER_PESO if optimize == 'cheapest' else Decimal('0')

    # State payload: (time, transfers, fare, legs, current_leg, path)
    start_state = (origin_id, 0)
    best_cost = {start_state: Decimal('0')}
    counter = 0
    queue = [(
        Decimal('0'), counter, origin_id, 0,
        Decimal('0'), Decimal('0'), 0, [], None, [origin_id],
    )]
    visited = set()

    while queue:
        (
            cost, _, terminal_id, route_id,
            elapsed, fare, transfers, legs, current_leg, path,
        ) = heapq.heappop(queue)

        state = (terminal_id, route_id)
        if state in visited:
            continue
        visited.add(state)

        if terminal_id == destination_id:
            finished = list(legs)
            if current_leg:
                finished.append(current_leg)
            return _assemble(graph, finished, elapsed, fare, transfers, path, optimize)

        if transfers >= max_transfers:
            continue

        for next_route_id, next_terminal, segment_time, segment_distance in graph['edges'].get(
            terminal_id, []
        ):
            next_state = (next_terminal, next_route_id)
            if next_state in visited:
                continue

            route = graph['routes'][next_route_id]
            time2 = elapsed + segment_time
            transfers2 = transfers
            fare2 = fare
            legs2 = legs
            current2 = current_leg

            if route_id == next_route_id and current_leg is not None:
                # Continue riding the same line.
                distance2 = current_leg['distance'] + segment_distance
                time_on_leg = current_leg['time'] + segment_time
                current2 = {**current_leg, 'stops': current_leg['stops'] + [next_terminal],
                            'distance': distance2, 'time': time_on_leg}
                fare2 = fare + route.fare_per_km * segment_distance
            else:
                # Board (or transfer onto) this line.
                if route_id != 0:
                    transfers2 = transfers + 1
                    time2 += TRANSFER_PENALTY_MINUTES
                fare2 = fare + route.base_fare + route.fare_per_km * segment_distance
                if current_leg:
                    legs2 = legs + [current_leg]
                current2 = {
                    'route': route,
                    'board': terminal_id,
                    'stops': [terminal_id, next_terminal],
                    'distance': segment_distance,
                    'time': segment_time,
                }

            new_cost = time2 + transfers2 * TRANSFER_PENALTY_MINUTES + fare2 * fare_weight
            if new_cost >= best_cost.get(next_state, Decimal('Infinity')):
                continue
            best_cost[next_state] = new_cost
            counter += 1
            heapq.heappush(queue, (
                new_cost, counter, next_terminal, next_route_id,
                time2, fare2, transfers2, legs2, current2, path + [next_terminal],
            ))

    return {'found': False, 'reason': 'no_path'}


def _assemble(graph, legs, elapsed, fare, transfers, path, optimize):
    """Turn raw Dijkstra results into a JSON friendly journey payload."""
    serialised_legs = []
    total_distance = Decimal('0')
    leg_time = Decimal('0')

    for leg in legs:
        route = leg['route']
        payload = _leg_payload(
            route,
            leg['board'],
            leg['stops'],
            leg['distance'],
            leg['time'],
        )
        serialised_legs.append(payload)
        total_distance += Decimal(str(payload['distance_km']))
        leg_time += Decimal(str(payload['time_minutes']))

    transfer_time = Decimal(transfers) * TRANSFER_PENALTY_MINUTES
    journey = {
        'found': True,
        'optimize': optimize,
        'legs': serialised_legs,
        'path': path,
        'transfers': transfers,
        'total_time_minutes': float(money(elapsed)),
        'riding_time_minutes': float(money(leg_time)),
        'transfer_time_minutes': float(money(transfer_time)),
        'total_fare': float(money(fare)),
        'total_distance_km': float(money(total_distance)),
    }
    journey['steps'] = _build_steps(journey)
    return journey
