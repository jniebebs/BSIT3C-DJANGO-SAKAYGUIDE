"""Seed the SakayGuide network with a small Metro Manila sample dataset.

Usage: python manage.py seed_sakay
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.sakay.models import Advisory, Route, RouteStop, Terminal, TransportMode

MODES = [
    {'name': 'Bus', 'slug': 'bus', 'icon': 'bus', 'color': '#2563eb', 'avg_speed_kmh': '24'},
    {'name': 'Jeepney', 'slug': 'jeepney', 'icon': 'jeepney', 'color': '#f59e0b', 'avg_speed_kmh': '15'},
    {'name': 'Train', 'slug': 'train', 'icon': 'train', 'color': '#16a34a', 'avg_speed_kmh': '40'},
    {'name': 'Multicab', 'slug': 'multicab', 'icon': 'multicab', 'color': '#0891b2', 'avg_speed_kmh': '18'},
    {'name': 'Tricycle', 'slug': 'tricycle', 'icon': 'tricycle', 'color': '#db2777', 'avg_speed_kmh': '12'},
    {'name': 'UV Express', 'slug': 'uv-express', 'icon': 'uvexpress', 'color': '#7c3aed', 'avg_speed_kmh': '20'},
]

TERMINALS = [
    {'name': 'PITX - Parañaque Integrated Terminal Exchange', 'municipality': 'Parañaque',
     'province': 'Metro Manila', 'landmark': 'EDSA extension, corner of Ninoy Aquino Avenue',
     'latitude': '14.511000', 'longitude': '120.990000', 'modes': ['bus', 'jeepney', 'multicab']},
    {'name': 'Baclaran Terminal', 'municipality': 'Parañaque',
     'province': 'Metro Manila', 'landmark': 'In front of Baclaran Church',
     'latitude': '14.534700', 'longitude': '120.988000', 'modes': ['jeepney', 'tricycle']},
    {'name': 'Pasay Rotonda Terminal', 'municipality': 'Pasay',
     'province': 'Metro Manila', 'landmark': 'Pasay Rotonda, EDSA corner Taft Avenue',
     'latitude': '14.534000', 'longitude': '120.999000', 'modes': ['jeepney', 'bus', 'multicab']},
    {'name': 'Taft Avenue Terminal', 'municipality': 'Pasay',
     'province': 'Metro Manila', 'landmark': 'Beside LRT-1 EDSA station',
     'latitude': '14.539100', 'longitude': '121.001900', 'modes': ['train', 'jeepney', 'bus']},
    {'name': 'Lawton Terminal', 'municipality': 'Manila',
     'province': 'Metro Manila', 'landmark': 'Across Manila City Hall',
     'latitude': '14.589700', 'longitude': '120.983700', 'modes': ['bus', 'jeepney', 'tricycle']},
    {'name': 'Sampaloc Terminal', 'municipality': 'Manila',
     'province': 'Metro Manila', 'landmark': 'UST España gate, Sampaloc',
     'latitude': '14.601000', 'longitude': '120.986500', 'modes': ['tricycle', 'jeepney']},
    {'name': 'Monumento Terminal', 'municipality': 'Caloocan',
     'province': 'Metro Manila', 'landmark': 'Monumento Rotonda, Rizal Avenue',
     'latitude': '14.655600', 'longitude': '120.984200', 'modes': ['bus', 'jeepney', 'uv-express']},
    {'name': 'North EDSA Terminal', 'municipality': 'Quezon City',
     'province': 'Metro Manila', 'landmark': 'Trinoma mall, North Avenue',
     'latitude': '14.654400', 'longitude': '121.032700', 'modes': ['train', 'bus', 'uv-express']},
    {'name': 'Cubao Terminal', 'municipality': 'Quezon City',
     'province': 'Metro Manila', 'landmark': 'Araneta City, EDSA corner Aurora Boulevard',
     'latitude': '14.619000', 'longitude': '121.046000', 'modes': ['train', 'bus', 'jeepney', 'uv-express']},
    {'name': 'Ortigas Terminal', 'municipality': 'Pasig',
     'province': 'Metro Manila', 'landmark': 'Ortigas Center, EDSA corner Ortigas Avenue',
     'latitude': '14.581900', 'longitude': '121.054400', 'modes': ['bus', 'jeepney', 'uv-express']},
    {'name': 'Ayala Terminal Makati', 'municipality': 'Makati',
     'province': 'Metro Manila', 'landmark': 'Ayala Triangle, Makati Central Business District',
     'latitude': '14.549000', 'longitude': '121.026000', 'modes': ['train', 'bus', 'jeepney', 'multicab']},
    {'name': 'Alabang Terminal', 'municipality': 'Muntinlupa',
     'province': 'Metro Manila', 'landmark': 'Alabang-Zapote Road, Festival Mall area',
     'latitude': '14.415000', 'longitude': '121.040000', 'modes': ['multicab', 'bus', 'jeepney']},
]

ROUTES = [
    {
        'code': 'MRT-3', 'name': 'North EDSA - Taft Avenue (MRT-3)',
        'mode': 'train', 'base_fare': '15.00', 'fare_per_km': '1.50',
        'dwell_time_seconds': 45,
        'origin': 'North EDSA Terminal', 'destination': 'Taft Avenue Terminal',
        'stops': [
            ('North EDSA Terminal', '0'),
            ('Cubao Terminal', '6.00'),
            ('Ayala Terminal Makati', '13.00'),
            ('Taft Avenue Terminal', '16.50'),
        ],
    },
    {
        'code': 'BUS-S1', 'name': 'PITX - Monumento City Bus',
        'mode': 'bus', 'base_fare': '20.00', 'fare_per_km': '2.50',
        'dwell_time_seconds': 60,
        'origin': 'PITX - Parañaque Integrated Terminal Exchange', 'destination': 'Monumento Terminal',
        'stops': [
            ('PITX - Parañaque Integrated Terminal Exchange', '0'),
            ('Pasay Rotonda Terminal', '4.00'),
            ('Taft Avenue Terminal', '5.50'),
            ('Lawton Terminal', '7.50'),
            ('Monumento Terminal', '10.00'),
        ],
    },
    {
        'code': 'JEEP-01', 'name': 'Baclaran - PITX Jeepney',
        'mode': 'jeepney', 'base_fare': '13.00', 'fare_per_km': '2.00',
        'dwell_time_seconds': 30,
        'origin': 'Baclaran Terminal', 'destination': 'PITX - Parañaque Integrated Terminal Exchange',
        'stops': [
            ('Baclaran Terminal', '0'),
            ('Pasay Rotonda Terminal', '2.50'),
            ('PITX - Parañaque Integrated Terminal Exchange', '5.50'),
        ],
    },
    {
        'code': 'JEEP-02', 'name': 'Cubao - Ayala Jeepney',
        'mode': 'jeepney', 'base_fare': '13.00', 'fare_per_km': '2.00',
        'dwell_time_seconds': 30,
        'origin': 'Cubao Terminal', 'destination': 'Ayala Terminal Makati',
        'stops': [
            ('Cubao Terminal', '0'),
            ('Ortigas Terminal', '4.50'),
            ('Ayala Terminal Makati', '9.00'),
        ],
    },
    {
        'code': 'MCAB-1', 'name': 'Ayala - Alabang Multicab',
        'mode': 'multicab', 'base_fare': '15.00', 'fare_per_km': '2.00',
        'dwell_time_seconds': 30,
        'origin': 'Ayala Terminal Makati', 'destination': 'Alabang Terminal',
        'stops': [
            ('Ayala Terminal Makati', '0'),
            ('Taft Avenue Terminal', '3.50'),
            ('Alabang Terminal', '11.00'),
        ],
    },
    {
        'code': 'TRYC-1', 'name': 'Lawton - Sampaloc Tricycle',
        'mode': 'tricycle', 'base_fare': '13.00', 'fare_per_km': '1.50',
        'dwell_time_seconds': 30,
        'origin': 'Lawton Terminal', 'destination': 'Sampaloc Terminal',
        'stops': [
            ('Lawton Terminal', '0'),
            ('Sampaloc Terminal', '3.00'),
        ],
    },
    {
        'code': 'UVX-1', 'name': 'Monumento - Cubao UV Express',
        'mode': 'uv-express', 'base_fare': '25.00', 'fare_per_km': '2.50',
        'dwell_time_seconds': 45,
        'origin': 'Monumento Terminal', 'destination': 'Cubao Terminal',
        'stops': [
            ('Monumento Terminal', '0'),
            ('Cubao Terminal', '5.00'),
        ],
    },
    {
        'code': 'BUS-S2', 'name': 'North EDSA - PITX Express Bus',
        'mode': 'bus', 'base_fare': '25.00', 'fare_per_km': '2.50',
        'dwell_time_seconds': 60,
        'origin': 'North EDSA Terminal', 'destination': 'PITX - Parañaque Integrated Terminal Exchange',
        'stops': [
            ('North EDSA Terminal', '0'),
            ('Cubao Terminal', '6.00'),
            ('Ayala Terminal Makati', '13.00'),
            ('Pasay Rotonda Terminal', '17.00'),
            ('PITX - Parañaque Integrated Terminal Exchange', '22.00'),
        ],
    },
]

ADVISORIES = [
    {
        'title': 'EDSA-Taft train delays this rush hour',
        'message': 'MRT-3 northbound trains are running 8-10 minutes late due to a signal check.',
        'category': 'delay', 'severity': 'warning', 'reported_by': 'SakayGuide community',
        'route_codes': ['MRT-3'],
    },
    {
        'title': 'Flooding along Taft Avenue',
        'message': 'Knee-deep flood near Pasay Rotonda after heavy rain. Jeepneys are rerouting via Roxas Boulevard.',
        'category': 'flooding', 'severity': 'critical', 'reported_by': 'kuya_marvs',
        'route_codes': ['BUS-S1', 'JEEP-01'],
    },
    {
        'title': 'Road reblocking on España',
        'message': 'One lane closed on España Boulevard tonight 10PM-5AM. Tricycle service to Sampaloc continues.',
        'category': 'roadwork', 'severity': 'info', 'reported_by': 'SakayGuide community',
        'route_codes': ['TRYC-1'],
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
