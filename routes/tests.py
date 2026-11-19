"""Read-only network tests for the Find My Route journey engine.

These tests use the live ``sakayguide_db`` through the test MIRROR alias, so
they never create or change tables; the journey search itself is read-only.
"""
from django.test import TestCase

from .models import Location
from .services import LEG_COLORS, find_journeys


class NetworkSearchTests(TestCase):
    databases = {'sakayguide'}

    def test_every_active_pair_is_searchable(self):
        locations = list(
            Location.objects.filter(status='active').order_by('location_id')
        )
        missing = []
        for origin in locations:
            for destination in locations:
                if origin.pk == destination.pk:
                    continue
                journeys = find_journeys(
                    origin.pk, destination.pk,
                    origin=origin, destination=destination,
                    include_map=False,
                )
                if not journeys:
                    missing.append(
                        (origin.location_name, destination.location_name)
                    )
        self.assertEqual(missing, [])

    def test_unknown_fare_is_reported_never_faked(self):
        locations = list(
            Location.objects.filter(status='active').order_by('location_id')
        )
        checked = 0
        for origin in locations:
            for destination in locations:
                if origin.pk == destination.pk:
                    continue
                for journey in find_journeys(
                    origin.pk, destination.pk,
                    origin=origin, destination=destination,
                    include_map=False,
                ):
                    unknown_legs = [
                        leg['route'].route_code
                        for leg in journey['legs']
                        if not leg.get('fare_recorded')
                    ]
                    if not unknown_legs:
                        continue
                    checked += 1
                    self.assertIsNone(journey['total_fare'])
                    self.assertFalse(journey['fare_known'])
                    for route_code in unknown_legs:
                        self.assertIn(
                            route_code, journey['unknown_fare_routes'],
                        )
        # The current network contains routes with no fare record; the test
        # keeps that fact visible instead of letting a zero/other amount leak.
        self.assertGreater(checked, 0)

    def test_every_journey_has_real_instructions(self):
        origin = Location.objects.filter(status='active').order_by('pk').first()
        destination = (
            Location.objects.filter(status='active')
            .exclude(pk=origin.pk)
            .order_by('pk')
            .first()
        )
        for journey in find_journeys(
            origin.pk, destination.pk,
            origin=origin, destination=destination,
        ):
            self.assertTrue(journey['legs'])
            self.assertTrue(journey['steps'])
            for transfer in journey['transfers']:
                self.assertTrue(transfer['location_name'])
                self.assertTrue(transfer['from_code'])
                self.assertTrue(transfer['to_code'])
                self.assertTrue(transfer['instructions'])

    def test_map_payload_uses_blue_ride_paths(self):
        origin = Location.objects.get(location_name='Bantayan', status='active')
        destination = Location.objects.get(location_name='Tapi', status='active')
        for journey in find_journeys(
            origin.pk, destination.pk,
            origin=origin, destination=destination,
        ):
            map_payload = journey['map']
            self.assertTrue(map_payload['journey_available'])
            self.assertTrue(map_payload['origin']['verified'])
            self.assertTrue(map_payload['destination']['verified'])
            for leg in map_payload['legs']:
                self.assertIn(leg['color'], LEG_COLORS)
