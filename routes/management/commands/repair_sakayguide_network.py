"""Repair the recorded SakayGuide network so every valid pair is searchable."""
from django.core.management.base import BaseCommand

from routes.network_repair import repair_network


class Command(BaseCommand):
    help = (
        'Restore rotated barangay location names, point the KAB-JP-0xx '
        'jeepney routes at the barangays named in their titles, and add the '
        'recorded origin/destination as ordered stops where they are missing. '
        'Fares are never invented: routes without an active regular fare stay '
        'marked as "fare not recorded".'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        result = repair_network(apply=not dry_run)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'DRY RUN - no changes were written. Re-run without '
                '--dry-run to apply them.'
            ))

        names = result['location_names']
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Location names restored: {len(names)}'
        ))
        for location_id, old_name, new_name in names:
            self.stdout.write(
                f'  location {location_id}: {old_name!r} -> {new_name!r}'
            )

        endpoints = result['route_endpoints']
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Route endpoints corrected: {len(endpoints)}'
        ))
        for route_id, old_origin, new_origin, old_destination, new_destination in endpoints:
            self.stdout.write(
                f'  route {route_id}: origin {old_origin!r} -> '
                f'{new_origin!r}; destination {old_destination!r} -> '
                f'{new_destination!r}'
            )

        stop_changes = result['route_stops']
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Routes given missing endpoint stops: {len(stop_changes)}'
        ))
        for route_code, actions in stop_changes:
            for action in actions:
                self.stdout.write(f'  {route_code}: {action}')

        missing_fares = result['routes_without_fare']
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Routes without an active regular fare: {len(missing_fares)}'
        ))
        if missing_fares:
            codes = ', '.join(route.route_code for route in missing_fares)
            self.stdout.write(
                '  These journeys will show "fare not recorded" instead of a '
                f'guessed amount: {codes}'
            )

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(
                'SakayGuide network repair completed.'
            ))
