"""Plain-dict serializers shared by the SakayGuide API views."""
from .models import money


def transport_mode_json(mode):
    return {
        'id': mode.id,
        'name': mode.name,
        'slug': mode.slug,
        'icon': mode.icon,
        'color': mode.color,
    }


def stop_json(stop, route=None):
    data = {
        'sequence': stop.sequence,
        'terminal_id': stop.terminal_id,
        'terminal': stop.terminal.name,
        'municipality': stop.terminal.municipality,
        'distance_from_origin_km': float(stop.distance_from_origin_km),
        'cumulative_fare': float(stop.cumulative_fare),
        'cumulative_time_minutes': float(stop.cumulative_time_minutes),
    }
    if route is not None:
        data['fare_to_here'] = float(stop.cumulative_fare)
        data['time_to_here_minutes'] = float(stop.cumulative_time_minutes)
    return data


def terminal_json(terminal, include_destinations=False, include_routes=False):
    modes = list(terminal.transport_modes.all())
    data = {
        'id': terminal.id,
        'name': terminal.name,
        'municipality': terminal.municipality,
        'province': terminal.province,
        'landmark': terminal.landmark,
        'latitude': float(terminal.latitude),
        'longitude': float(terminal.longitude),
        'coordinates': [float(terminal.latitude), float(terminal.longitude)],
        'description': terminal.description,
        'transport_modes': [transport_mode_json(mode) for mode in modes],
        'mode_labels': [mode.name for mode in modes],
    }
    if include_destinations:
        data['destinations'] = terminal.destinations()
    if include_routes:
        data['routes'] = [route_json(route) for route in terminal.served_routes()]
    return data


def route_json(route, include_stops=False):
    data = {
        'id': route.id,
        'code': route.code,
        'name': route.name,
        'transport_mode': transport_mode_json(route.transport_mode),
        'origin_terminal': {
            'id': route.origin_terminal_id,
            'name': route.origin_terminal.name,
        },
        'destination_terminal': {
            'id': route.destination_terminal_id,
            'name': route.destination_terminal.name,
        },
        'base_fare': float(route.base_fare),
        'fare_per_km': float(route.fare_per_km),
        'dwell_time_seconds': route.dwell_time_seconds,
        'bidirectional': route.bidirectional,
        'is_active': route.is_active,
        'stop_count': route.stops.count(),
    }
    if include_stops:
        data['stops'] = [stop_json(stop) for stop in route.stops.select_related('terminal')]
    return data


def advisory_json(advisory):
    return {
        'id': advisory.id,
        'title': advisory.title,
        'message': advisory.message,
        'category': advisory.category,
        'severity': advisory.severity,
        'status': advisory.status,
        'is_live': advisory.is_live,
        'terminal': (
            {'id': advisory.terminal_id, 'name': advisory.terminal.name}
            if advisory.terminal_id else None
        ),
        'routes': [
            {'id': route.id, 'code': route.code, 'name': route.name}
            for route in advisory.routes.all()
        ],
        'reported_by': advisory.reported_by,
        'upvotes': advisory.upvotes,
        'expires_at': advisory.expires_at.isoformat() if advisory.expires_at else None,
        'created_at': advisory.created_at.isoformat(),
    }


def fare_summary(route):
    """Headline fare/time figures used in terminal and route cards."""
    stops = list(route.stops.order_by('sequence'))
    end = len(stops) - 1
    if end < 1:
        return {
            'min_fare': float(money(route.base_fare)),
            'max_fare': float(money(route.base_fare)),
            'end_to_end_minutes': 0.0,
        }
    return {
        'min_fare': float(money(route.base_fare)),
        'max_fare': float(route.fare_between(0, end, stops)),
        'end_to_end_minutes': float(route.time_between_minutes(0, end, stops)),
    }
