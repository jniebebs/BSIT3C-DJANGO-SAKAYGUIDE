"""Seed the SakayGuide network with a Kabankalan City, Negros Occidental dataset.

Usage: python manage.py seed_sakay

WARNING: All records seeded by this command are unverified data. Terminal names,
coordinates, routes, distances, fares, and schedules must be confirmed against
official sources before being presented to commuters as real transportation
information. The project's geographic scope is strictly Kabankalan City,
Negros Occidental, Philippines only.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.sakay.models import Advisory, Route, RouteStop, Terminal, TransportMode

MODES = [
    {'name': 'Ceres Bus', 'slug': 'ceres-bus', 'icon': 'bus', 'color': '#2563eb', 'avg_speed_kmh': '30'},
    {'name': 'Jeepney', 'slug': 'jeepney', 'icon': 'jeepney', 'color': '#f59e0b', 'avg_speed_kmh': '20'},
    {'name': 'Tricycle', 'slug': 'tricycle', 'icon': 'tricycle', 'color': '#db2777', 'avg_speed_kmh': '15'},
    {'name': 'Van', 'slug': 'van', 'icon': 'van', 'color': '#7c3aed', 'avg_speed_kmh': '25'},
]

TERMINALS = [
    {
        'name': 'Kabankalan City Public Terminal',
        'municipality': 'Kabankalan City',
        'province': 'Negros Occidental',
        'landmark': 'Near the city center, Kabankalan City',
        'latitude': '9.985700',
        'longitude': '122.813800',
        'modes': ['ceres-bus', 'jeepney', 'tricycle', 'van'],
    },
    {
        'name': 'Barangay Camansi Terminal',
        'municipality': 'Kabankalan City',
        'province': 'Negros Occidental',
        'landmark': 'Barangay Camansi, Kabankalan City',
        'latitude': '9.947726',
        'longitude': '122.799360',
        'modes': ['jeepney', 'tricycle'],
    },
    {
        'name': 'Barangay Inapoy Terminal',
        'municipality': 'Kabankalan City',
        'province': 'Negros Occidental',
        'landmark': 'Barangay Inapoy, Kabankalan City',
        'latitude': '9.815193',
        'longitude': '122.863516',
        'modes': ['tricycle'],
    },
]

ROUTES = [
    {
        'code': 'RTE-001',
        'name': 'Kabankalan Downtown Loop',
        'mode': 'jeepney',
        'base_fare': '13.00',
        'fare_per_km': '2.00',
        'dwell_time_seconds': 60,
        'origin': 'Kabankalan City Public Terminal',
        'destination': 'Kabankalan City Public Terminal',
        'stops': [
            ('Kabankalan City Public Terminal', '0'),
            ('Barangay Camansi Terminal', '3.50'),
            ('Barangay Inapoy Terminal', '7.00'),
        ],
    },
    {
        'code': 'RTE-002',
        'name': 'Kabankalan to Camansi Jeepney',
        'mode': 'jeepney',
        'base_fare': '13.00',
        'fare_per_km': '2.00',
        'dwell_time_seconds': 30,
        'origin': 'Kabankalan City Public Terminal',
        'destination': 'Barangay Camansi Terminal',
        'stops': [
            ('Kabankalan City Public Terminal', '0'),
            ('Barangay Camansi Terminal', '3.50'),
        ],
    },
    {
        'code': 'RTE-003',
        'name': 'Kabankalan Ceres Bus Provincial',
        'mode': 'ceres-bus',
        'base_fare': '25.00',
        'fare_per_km': '2.50',
        'dwell_time_seconds': 60,
        'origin': 'Kabankalan City Public Terminal',
        'destination': 'Barangay Inapoy Terminal',
        'stops': [
            ('Kabankalan City Public Terminal', '0'),
            ('Barangay Camansi Terminal', '12.00'),
            ('Barangay Inapoy Terminal', '25.00'),
        ],
    },
    {
        'code': 'RTE-004',
        'name': 'Inapoy Tricycle Route',
        'mode': 'tricycle',
        'base_fare': '13.00',
        'fare_per_km': '1.50',
        'dwell_time_seconds': 30,
        'origin': 'Barangay Inapoy Terminal',
        'destination': 'Kabankalan City Public Terminal',
        'stops': [
            ('Barangay Inapoy Terminal', '0'),
            ('Kabankalan City Public Terminal', '7.00'),
        ],
    },
]

ADVISORIES = [
    {
        'title': 'Route data pending verification',
        'message': 'All Kabankalan City routes, fares, and schedules shown are unverified records. Verify with local operators before travel.',
        'category': 'other',
        'severity': 'info',
        'reported_by': 'SakayGuide administrator',
        'route_codes': [],
    },
]


class Command(BaseCommand):
    help = 'Seed SakayGuide terminals, routes, stops and community advisories.'

    def handle(self, *args, **options):
        modes = {}
        for mode_data in MODES:
            mode, _ = TransportMode.objects.update_or_create(
                slug=mode_data['slug'],
                defaults={
                    'name': mode_data['name'],
                    'icon': mode_data['icon'],
                    'color': mode_data['color'],
                    'avg_speed_kmh': Decimal(mode_data['avg_speed_kmh']),
                },
            )
            modes[mode.slug] = mode
        self.stdout.write(f'  modes: {len(modes)}')

        terminals = {}
        for terminal_data in TERMINALS:
            terminal_data = dict(terminal_data)
            mode_slugs = terminal_data.pop('modes')
            terminal, _ = Terminal.objects.update_or_create(
                name=terminal_data['name'],
                defaults=terminal_data,
            )
            terminal.transport_modes.set([modes[slug] for slug in mode_slugs])
            terminals[terminal.name] = terminal
        self.stdout.write(f'  terminals: {len(terminals)}')

        for route_data in ROUTES:
            route_data = dict(route_data)
            stop_rows = route_data.pop('stops')
            origin_name = route_data.pop('origin')
            destination_name = route_data.pop('destination')
            route, _ = Route.objects.update_or_create(
                code=route_data['code'],
                defaults={
                    'name': route_data['name'],
                    'transport_mode': modes[route_data['mode']],
                    'origin_terminal': terminals[origin_name],
                    'destination_terminal': terminals[destination_name],
                    'base_fare': Decimal(route_data['base_fare']),
                    'fare_per_km': Decimal(route_data['fare_per_km']),
                    'dwell_time_seconds': route_data['dwell_time_seconds'],
                    'is_active': True,
                },
            )
            RouteStop.objects.filter(route=route).delete()
            for sequence, (terminal_name, distance) in enumerate(stop_rows, start=1):
                RouteStop.objects.create(
                    route=route,
                    terminal=terminals[terminal_name],
                    sequence=sequence,
                    distance_from_origin_km=Decimal(distance),
                )
            route.recompute_fare_matrix()
            route_data['mode'] = route.transport_mode.slug
            route_data['origin'] = origin_name
            route_data['destination'] = destination_name
            route_data['stops'] = stop_rows
        self.stdout.write(f'  routes: {len(ROUTES)}')

        for advisory_data in ADVISORIES:
            advisory_data = dict(advisory_data)
            route_codes = advisory_data.pop('route_codes')
            advisory, created = Advisory.objects.get_or_create(
                title=advisory_data['title'],
                defaults=advisory_data,
            )
            if created:
                advisory.routes.set(Route.objects.filter(code__in=route_codes))
        self.stdout.write(f'  advisories: {len(ADVISORIES)}')

        self.stdout.write(self.style.SUCCESS('SakayGuide data seeded.'))
