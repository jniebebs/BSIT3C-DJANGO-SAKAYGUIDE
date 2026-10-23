"""Public JSON endpoints powering the SakayGuide frontend."""
import json

from django.contrib.auth.decorators import login_required
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import get_token
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import Advisory, Route, SavedRoute, SearchHistory, Terminal
from .routing import OPTIMIZE_CHOICES, plan_journey
from .serializers import (
    advisory_json,
    fare_summary,
    route_json,
    stop_json,
    terminal_json,
)

DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50


def _parse_limit(raw):
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SEARCH_LIMIT
    return max(1, min(limit, MAX_SEARCH_LIMIT))


def terminal_search(request):
    """Fuzzy (ILIKE style) search over terminal names, cities and landmarks.

    GET /api/terminals/search?q=pitx&limit=10

    Results are restricted to terminals within Kabankalan City, Negros
    Occidental to match the project's geographic scope.
    """
    query = request.GET.get('q', '').strip()
    limit = _parse_limit(request.GET.get('limit'))

    terminals = (
        Terminal.objects.prefetch_related('transport_modes')
        .filter(municipality='Kabankalan City', province='Negros Occidental')
        .order_by('name')
    )

    if query:
        # Every whitespace separated token must match at least one field,
        # which behaves like SQL ILIKE '%token%' across all of them.
        combined = Q()
        for token in query.split():
            combined &= (
                Q(name__icontains=token)
                | Q(municipality__icontains=token)
                | Q(province__icontains=token)
                | Q(landmark__icontains=token)
            )
        terminals = terminals.filter(combined).annotate(
            rank=Case(
                When(name__iexact=query, then=Value(0)),
                When(name__istartswith=query, then=Value(1)),
                When(municipality__istartswith=query, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        ).order_by('rank', 'name')

    results = [
        terminal_json(terminal, include_destinations=True)
        for terminal in terminals[:limit]
    ]
    return JsonResponse({
        'query': query,
        'count': len(results),
        'results': results,
    })


@require_GET
def terminal_detail(request, pk):
    """Full terminal payload used by the details card."""
    terminal = Terminal.objects.filter(pk=pk).prefetch_related('transport_modes').first()
    if terminal is None:
        return JsonResponse({'error': 'Terminal not found.'}, status=404)
    return JsonResponse(
        terminal_json(terminal, include_destinations=True, include_routes=True)
    )


@require_GET
def terminal_routes(request, pk):
    """Active routes serving a terminal with headline fares/times."""
    terminal = Terminal.objects.filter(pk=pk).first()
    if terminal is None:
        return JsonResponse({'error': 'Terminal not found.'}, status=404)
    routes = []
    for route in terminal.served_routes():
        payload = route_json(route)
        payload['fare_summary'] = fare_summary(route)
        routes.append(payload)
    return JsonResponse({
        'terminal': {'id': terminal.id, 'name': terminal.name},
        'count': len(routes),
        'routes': routes,
    })


@require_GET
def route_list(request):
    """List active routes, optionally filtered by mode slug or terminal id.

    Routes are restricted to those whose origin and destination terminals are
    both within Kabankalan City, Negros Occidental.
    """
    routes = (
        Route.objects.filter(is_active=True)
        .filter(origin_terminal__municipality='Kabankalan City', origin_terminal__province='Negros Occidental')
        .filter(destination_terminal__municipality='Kabankalan City', destination_terminal__province='Negros Occidental')
        .select_related('transport_mode', 'origin_terminal', 'destination_terminal')
    )

    mode_slug = request.GET.get('mode')
    if mode_slug:
        routes = routes.filter(transport_mode__slug=mode_slug)

    terminal_id = request.GET.get('terminal')
    if terminal_id and terminal_id.isdigit():
        routes = routes.filter(stops__terminal_id=int(terminal_id)).distinct()

    payloads = [route_json(route) for route in routes.order_by('code')]
    return JsonResponse({'count': len(payloads), 'routes': payloads})


@require_GET
def route_detail(request, pk):
    """Single route with its ordered stops and cumulative fare/time columns."""
    route = Route.objects.filter(pk=pk).select_related(
        'transport_mode', 'origin_terminal', 'destination_terminal'
    ).first()
    if route is None:
        return JsonResponse({'error': 'Route not found.'}, status=404)
    payload = route_json(route, include_stops=True)
    payload['fare_summary'] = fare_summary(route)
    return JsonResponse(payload)


@require_GET
def route_fare_matrix(request, pk):
    """Automated cumulative fare matrix and travel time table for a route.

    GET /api/routes/<id>/fare-matrix/
    """
    route = Route.objects.filter(pk=pk).select_related('transport_mode').first()
    if route is None:
        return JsonResponse({'error': 'Route not found.'}, status=404)

    route.recompute_fare_matrix()
    stops = list(route.stops.select_related('terminal').order_by('sequence'))
    if not stops:
        return JsonResponse({'error': 'Route has no stops.'}, status=404)

    return JsonResponse({
        'route': route_json(route),
        'stops': [stop_json(stop) for stop in stops],
        'matrix': route.fare_matrix(),
        'base_fare': float(route.base_fare),
        'fare_per_km': float(route.fare_per_km),
    })


@require_GET
def route_plan(request):
    """Multi-modal, multi-leg journey planner.

    GET /api/route-plan/?origin=1&destination=12&optimize=fastest
    """
    origin_raw = request.GET.get('origin')
    destination_raw = request.GET.get('destination')
    if not origin_raw or not destination_raw:
        return JsonResponse(
            {'error': 'Both "origin" and "destination" query parameters are required.'},
            status=400,
        )
    try:
        origin_id = int(origin_raw)
        destination_id = int(destination_raw)
    except (TypeError, ValueError):
        return JsonResponse({'error': '"origin" and "destination" must be terminal ids.'}, status=400)

    origin = Terminal.objects.filter(pk=origin_id).first()
    destination = Terminal.objects.filter(pk=destination_id).first()
    if origin is None or destination is None:
        return JsonResponse({'error': 'Terminal not found.'}, status=404)

    if origin.municipality != 'Kabankalan City' or origin.province != 'Negros Occidental':
        return JsonResponse(
            {'error': f'Origin terminal "{origin.name}" is outside the Kabankalan City service area.'},
            status=400,
        )
    if destination.municipality != 'Kabankalan City' or destination.province != 'Negros Occidental':
        return JsonResponse(
            {'error': f'Destination terminal "{destination.name}" is outside the Kabankalan City service area.'},
            status=400,
        )

    optimize = request.GET.get('optimize', 'fastest')
    if optimize not in OPTIMIZE_CHOICES:
        return JsonResponse(
            {'error': f'"optimize" must be one of: {", ".join(OPTIMIZE_CHOICES)}.'},
            status=400,
        )

    journey = plan_journey(origin_id, destination_id, optimize=optimize)
    journey['origin'] = terminal_json(origin)
    journey['destination'] = terminal_json(destination)
    if journey['found'] and journey['legs']:
        first = journey['legs'][0]['stops'][0]['name']
        last = journey['legs'][-1]['stops'][-1]['name']
        journey['summary'] = f'{first} to {last}'
    else:
        journey['summary'] = f'{origin.name} to {destination.name}'
    return JsonResponse(journey)


# ----------------------------------------------------------------------
# Community status / advisory feed
# ----------------------------------------------------------------------
@require_GET
def advisory_list(request):
    """Community transit advisories.

    GET /api/advisories/?live=1&route=3&terminal=5&category=delay&limit=20
    """
    limit = _parse_limit(request.GET.get('limit'))
    advisories = Advisory.objects.select_related('terminal').prefetch_related('routes')

    if request.GET.get('live') in ('1', 'true', 'yes'):
        advisories = advisories.filter(status='active').filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )

    route_id = request.GET.get('route')
    if route_id and route_id.isdigit():
        advisories = advisories.filter(routes__id=int(route_id))

    terminal_id = request.GET.get('terminal')
    if terminal_id and terminal_id.isdigit():
        advisories = advisories.filter(terminal_id=int(terminal_id))

    category = request.GET.get('category')
    if category:
        advisories = advisories.filter(category=category)

    severity = request.GET.get('severity')
    if severity:
        advisories = advisories.filter(severity=severity)

    advisories = advisories.order_by('-created_at')[:limit]
    results = [advisory_json(advisory) for advisory in advisories]
    return JsonResponse({'count': len(results), 'advisories': results})


def _read_json_body(request):
    """Parse a JSON request body, falling back to form data."""
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return None
    return request.POST.dict()


@require_POST
def advisory_create(request):
    """Submit a community advisory (anonymous reporting is allowed)."""
    data = _read_json_body(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    title = str(data.get('title', '')).strip()
    message = str(data.get('message', '')).strip()
    category = str(data.get('category', 'other')).strip() or 'other'
    severity = str(data.get('severity', 'info')).strip() or 'info'
    reported_by = str(data.get('reported_by', '')).strip()[:60]

    if not title or len(title) > 120:
        return JsonResponse({'error': 'Title is required (max 120 characters).'}, status=400)
    if not message or len(message) > 2000:
        return JsonResponse({'error': 'Message is required (max 2000 characters).'}, status=400)

    valid_categories = {choice[0] for choice in Advisory.CATEGORY_CHOICES}
    if category not in valid_categories:
        return JsonResponse({'error': f'Unknown category "{category}".'}, status=400)
    valid_severities = {choice[0] for choice in Advisory.SEVERITY_CHOICES}
    if severity not in valid_severities:
        return JsonResponse({'error': f'Unknown severity "{severity}".'}, status=400)

    terminal = None
    terminal_raw = data.get('terminal')
    if terminal_raw:
        try:
            terminal = Terminal.objects.get(pk=int(terminal_raw))
        except (Terminal.DoesNotExist, TypeError, ValueError):
            return JsonResponse({'error': 'Unknown terminal.'}, status=400)

    advisory = Advisory.objects.create(
        title=title,
        message=message,
        category=category,
        severity=severity,
        reported_by=reported_by,
        terminal=terminal,
    )

    route_ids = data.get('routes') or []
    if isinstance(route_ids, (str, int)):
        route_ids = [route_ids]
    valid_routes = Route.objects.filter(pk__in=[int(r) for r in route_ids if str(r).isdigit()])
    advisory.routes.set(valid_routes)

    return JsonResponse({'status': 'created', 'advisory': advisory_json(advisory)}, status=201)


@require_POST
def advisory_upvote(request, pk):
    """Upvote a community advisory so useful alerts rise to the top."""
    advisory = Advisory.objects.filter(pk=pk).first()
    if advisory is None:
        return JsonResponse({'error': 'Advisory not found.'}, status=404)
    Advisory.objects.filter(pk=pk).update(upvotes=advisory.upvotes + 1)
    advisory.refresh_from_db()
    return JsonResponse({'status': 'upvoted', 'upvotes': advisory.upvotes})


@login_required
@require_POST
def advisory_resolve(request, pk):
    """Mark a community advisory as resolved (staff/rider moderation)."""
    advisory = Advisory.objects.filter(pk=pk).first()
    if advisory is None:
        return JsonResponse({'error': 'Advisory not found.'}, status=404)
    advisory.status = 'resolved'
    advisory.save(update_fields=['status', 'updated_at'])
    return JsonResponse({'status': 'resolved', 'advisory': advisory_json(advisory)})


@require_GET
def csrf_token_view(request):
    """Ensure a CSRF cookie is issued so the React app can POST safely."""
    return JsonResponse({'csrfToken': get_token(request)})


# ----------------------------------------------------------------------
# Saved routes (commuter-facing)
# ----------------------------------------------------------------------
@login_required(login_url='login')
def saved_routes_page(request):
    """Render the commuter's saved routes page."""
    saved = (
        SavedRoute.objects.filter(user=request.user)
        .select_related('origin_terminal', 'destination_terminal')
        .order_by('-created_at')
    )
    return render(request, 'sakay/saved_routes.html', {'saved_routes': saved})


@require_POST
@login_required(login_url='login')
def save_route_ajax(request):
    """Save a route for the authenticated user.

    Expects JSON body: { origin_terminal_id, destination_terminal_id, name? }
    """
    data = _read_json_body(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    origin_id = data.get('origin_terminal_id')
    destination_id = data.get('destination_terminal_id')
    name = str(data.get('name', '')).strip()

    if not origin_id or not destination_id:
        return JsonResponse(
            {'error': 'origin_terminal_id and destination_terminal_id are required.'},
            status=400,
        )

    try:
        origin_id = int(origin_id)
        destination_id = int(destination_id)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Terminal ids must be integers.'}, status=400)

    origin = get_object_or_404(Terminal, pk=origin_id)
    destination = get_object_or_404(Terminal, pk=destination_id)

    if origin_id == destination_id:
        return JsonResponse(
            {'error': 'Origin and destination cannot be the same terminal.'},
            status=400,
        )

    saved, created = SavedRoute.objects.update_or_create(
        user=request.user,
        origin_terminal=origin,
        destination_terminal=destination,
        defaults={'name': name or ''},
    )

    return JsonResponse({
        'status': 'created' if created else 'updated',
        'saved_route': {
            'id': saved.id,
            'name': saved.name or f'{origin.name} → {destination.name}',
            'origin': {'id': origin.id, 'name': origin.name},
            'destination': {'id': destination.id, 'name': destination.name},
            'created_at': saved.created_at.isoformat(),
        },
    }, status=201 if created else 200)


@require_http_methods(['DELETE'])
@login_required(login_url='login')
def unsave_route_ajax(request, pk):
    """Remove a saved route. Only the owner may delete it."""
    saved = get_object_or_404(SavedRoute, pk=pk, user=request.user)
    saved.delete()
    return JsonResponse({'status': 'removed', 'id': pk})


@require_POST
@login_required(login_url='login')
def record_search_ajax(request):
    """Record a route search in the commuter's history.

    Expects JSON body: { origin_terminal_id, destination_terminal_id }
    """
    data = _read_json_body(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    origin_id = data.get('origin_terminal_id')
    destination_id = data.get('destination_terminal_id')

    if not origin_id or not destination_id:
        return JsonResponse(
            {'error': 'origin_terminal_id and destination_terminal_id are required.'},
            status=400,
        )

    try:
        origin_id = int(origin_id)
        destination_id = int(destination_id)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Terminal ids must be integers.'}, status=400)

    origin = get_object_or_404(Terminal, pk=origin_id)
    destination = get_object_or_404(Terminal, pk=destination_id)

    SearchHistory.objects.create(
        user=request.user,
        origin_terminal=origin,
        destination_terminal=destination,
    )

    return JsonResponse({'status': 'recorded'}, status=201)
