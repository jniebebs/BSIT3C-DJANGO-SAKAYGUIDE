"""Read-only network tests for the Find My Route journey engine.

These tests use the live ``sakayguide_db`` through the test MIRROR alias, so
they never create or change tables; the journey search itself is read-only.
They verify that every displayed amount comes from the latest saved
``route_fares`` row and that fares are recalculated per travelled segment.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import Location, Route, RouteFare
from .services import (
    LEG_COLORS,
    _haversine_km,
    _load_network,
    destination_summaries,
    fare_is_current,
    fares_version,
    find_journeys,
    latest_active_fares,
    transport_options,
    travel_minutes,
)


class NetworkSearchTests(TestCase):
    databases = {'sakayguide'}

    @classmethod
    def setUpTestData(cls):
        cls.locations = list(
            Location.objects.filter(status='active').order_by('location_id')
        )
        cls.network = _load_network()

    def test_every_journey_uses_recorded_network_records(self):
        """Every option is one direct ride or one recorded transfer.

        Legs join at the recorded transfer point, the first leg starts at
        the searched origin and the last leg ends at the searched
        destination. No leg, connection or fare is invented.
        """
        checked_pairs = 0
        checked_legs = 0
        for origin in self.locations:
            for destination in self.locations:
                if origin.pk == destination.pk:
                    continue
                journeys = find_journeys(
                    origin.pk, destination.pk,
                    origin=origin, destination=destination,
                    network=self.network, include_map=False,
                )
                checked_pairs += 1
                for journey in journeys:
                    legs = journey['legs']
                    self.assertIn(len(legs), (1, 2))
                    self.assertEqual(
                        journey['transfer_count'], len(legs) - 1,
                    )
                    self.assertEqual(
                        len(journey['transfers']), len(legs) - 1,
                    )
                    self.assertEqual(legs[0]['board_id'], origin.pk)
                    self.assertEqual(
                        legs[-1]['alight_id'], destination.pk,
                    )
                    for leg in legs:
                        self.assertEqual(
                            leg['minutes'],
                            travel_minutes(
                                leg['distance_km'],
                                leg['route'].transport_type.transport_name,
                                fallback_minutes=leg['minutes'],
                            ),
                            f"{leg['route'].route_code}: minutes must "
                            f"equal the km-based estimate for its distance",
                        )
                    self.assertEqual(
                        journey['ride_time'],
                        sum(leg['minutes'] for leg in legs),
                    )
                    self.assertEqual(
                        journey['total_time'],
                        journey['ride_time'] + journey['transfer_time'],
                    )
                    for first, second in zip(legs, legs[1:]):
                        self.assertEqual(
                            first['alight_id'], second['board_id'],
                        )
                        self.assertEqual(
                            first['transfer_after']['location_id'],
                            first['alight_id'],
                        )
                        self.assertEqual(
                            first['transfer_after']['location_name'],
                            first['alight_at'],
                        )
                    self.assertTrue(journey['steps'])
                    checked_legs += len(legs)
        self.assertGreater(checked_pairs, 0)
        self.assertGreater(checked_legs, 0)

    def test_recorded_transfer_journeys_are_offered_and_priced(self):
        """A recorded two-ride connection is returned and its fare is summed."""
        found = None
        for origin in self.locations:
            for destination in self.locations:
                if origin.pk == destination.pk:
                    continue
                journeys = find_journeys(
                    origin.pk, destination.pk,
                    origin=origin, destination=destination,
                    network=self.network, include_map=False,
                )
                found = next(
                    (j for j in journeys if len(j['legs']) == 2), None,
                )
                if found is not None:
                    break
            if found is not None:
                break

        self.assertIsNotNone(
            found, 'the recorded transfer network produced no journey',
        )
        transfer = found['transfers'][0]
        self.assertTrue(transfer['location_name'])
        self.assertTrue(transfer['from_code'])
        self.assertTrue(transfer['to_code'])
        self.assertTrue(transfer['instructions'])

        leg_fares = [leg['fare'] for leg in found['legs']]
        self.assertTrue(all(fare is not None for fare in leg_fares))
        self.assertEqual(
            found['ride_fare'], sum(leg_fares, Decimal('0.00')),
        )
        self.assertEqual(
            found['total_fare'],
            found['ride_fare'] + found['transfer_fare'],
        )
        self.assertTrue(found['fare_known'])

    def test_full_route_fare_equals_latest_saved_fare_row(self):
        """The full-route price is exactly the administrator's saved total."""
        current = latest_active_fares(
            RouteFare.objects.filter(status=RouteFare.STATUS_ACTIVE),
        )
        checked = 0
        for route in Route.objects.filter(status='active'):
            if route.origin_id == route.destination_id:
                continue
            fare_record = current.get((route.pk, 1))
            if fare_record is None:
                continue
            journeys = find_journeys(
                route.origin_id, route.destination_id,
                network=self.network, include_map=False,
            )
            matching = [
                leg
                for journey in journeys
                for leg in journey['legs']
                if leg['route_id'] == route.pk
                and leg['board_id'] == route.origin_id
                and leg['alight_id'] == route.destination_id
            ]
            self.assertTrue(
                matching,
                f'no full-route leg found for {route.route_code}',
            )
            for leg in matching:
                self.assertEqual(
                    leg['fare'], fare_record.total_estimated_fare,
                    f'{route.route_code} full-route fare must use the '
                    f'latest saved total',
                )
            checked += 1
        self.assertGreater(checked, 0)

    def test_travel_time_is_recalculated_from_distance(self):
        """Minutes follow the ridden distance, not a fixed full-route time.

        A shorter origin/destination pair on the same route takes less time
        than the full ride, and every leg uses the one km-based formula the
        commuter pages display.
        """
        route = Route.objects.get(route_code='KAB-JP-01')
        stops = list(
            route.stops.select_related('location').order_by('stop_order')
        )
        origin = stops[0].location
        destination = stops[-1].location
        middle = stops[len(stops) // 2].location

        def leg_between(first, second):
            for journey in find_journeys(
                first.pk, second.pk, network=self.network,
                include_map=False,
            ):
                for leg in journey['legs']:
                    if (
                        leg['route_id'] == route.pk
                        and leg['board_id'] == first.pk
                        and leg['alight_id'] == second.pk
                    ):
                        return leg
            return None

        full = leg_between(origin, destination)
        partial = leg_between(middle, destination)
        self.assertIsNotNone(full)
        self.assertIsNotNone(partial)
        self.assertEqual(
            full['minutes'],
            travel_minutes(full['distance_km'], 'Jeepney'),
        )
        self.assertLess(partial['distance_km'], full['distance_km'])
        self.assertEqual(
            partial['minutes'],
            travel_minutes(partial['distance_km'], 'Jeepney'),
        )
        self.assertLess(partial['minutes'], full['minutes'])

    def test_zigzag_stop_order_does_not_collapse_travel_time(self):
        """An alphabetically ordered stop list is not a 380 km ride.

        KAB-JP-07 stores its barangays alphabetically, so summing distances
        in that order gives a path far longer than the route itself. The leg
        must use the straight board-to-alight distance, which keeps its
        minutes proportional instead of collapsing a 12 km hop to one minute.
        """
        route = Route.objects.get(route_code='KAB-JP-07')
        origin = route.origin
        destination = route.destination
        journeys = find_journeys(
            origin.pk, destination.pk, network=self.network,
            include_map=False,
        )
        full = next(
            leg
            for journey in journeys
            for leg in journey['legs']
            if leg['route_id'] == route.pk
            and leg['board_id'] == origin.pk
            and leg['alight_id'] == destination.pk
        )
        straight_km = _haversine_km(
            origin.latitude, origin.longitude,
            destination.latitude, destination.longitude,
        )
        self.assertLess(full['distance_km'], straight_km + 0.5)
        self.assertEqual(
            full['minutes'],
            travel_minutes(full['distance_km'], 'Jeepney'),
        )

        stops = {
            stop.location.location_name: stop.location
            for stop in route.stops.select_related('location')
        }
        first, second = stops['Tagoc'], stops['Talubangi']
        shortest = next(
            leg
            for journey in find_journeys(
                first.pk, second.pk, network=self.network,
                include_map=False,
            )
            for leg in journey['legs']
            if leg['route_id'] == route.pk
            and {leg['board_id'], leg['alight_id']} == {first.pk, second.pk}
        )
        self.assertLess(shortest['distance_km'], straight_km)
        self.assertGreater(shortest['minutes'], 1)
        self.assertEqual(
            shortest['minutes'],
            travel_minutes(shortest['distance_km'], 'Jeepney'),
        )

    def test_travel_minutes_follow_transport_speed(self):
        """The shared formula: Jeepney 20 km/h, Tricycle 15 km/h.

        This is the single calculation behind the dropdown annotation, the
        results summary, the fastest badge, the option cards, the route
        details panel and the map label, so no section can disagree.
        """
        self.assertEqual(travel_minutes(10.0, 'Jeepney'), 30)
        self.assertEqual(travel_minutes(10.0, 'Tricycle'), 40)
        self.assertEqual(travel_minutes(7.5, 'Tricycle'), 30)
        self.assertEqual(travel_minutes(0.28, 'Tricycle'), 1)
        self.assertEqual(travel_minutes(12.56, 'Jeepney'), 38)
        # Unrecognised registered modes fall back to the jeepney speed.
        self.assertEqual(travel_minutes(10.0, 'SQLLAB SHUTTLE'), 30)
        # No known distance: the recorded estimate stands in untouched.
        self.assertEqual(travel_minutes(0.0, 'Jeepney', 12), 12)
        self.assertEqual(travel_minutes(0.0, 'Jeepney'), 0)
        # A long, slow leg still rounds to the nearest minute, never zero.
        self.assertEqual(travel_minutes(0.1, 'Tricycle'), 1)

    def test_segment_fares_stay_within_the_saved_bounds(self):
        """A segment is never cheaper than minimum or dearer than the total."""
        checked = 0
        partial_cheaper = 0
        for origin in self.locations:
            for destination in self.locations:
                if origin.pk == destination.pk:
                    continue
                for journey in find_journeys(
                    origin.pk, destination.pk,
                    origin=origin, destination=destination,
                    network=self.network, include_map=False,
                ):
                    for leg in journey['legs']:
                        record = leg['fare_record']
                        if record is None:
                            self.assertIsNone(leg['fare'])
                            continue
                        checked += 1
                        self.assertGreaterEqual(
                            leg['fare'], record.minimum_fare,
                        )
                        self.assertLessEqual(
                            leg['fare'], record.total_estimated_fare,
                        )
                        self.assertEqual(
                            leg['fare'],
                            leg['fare'].quantize(Decimal('0.01')),
                        )
                        if (
                            leg['board_id'], leg['alight_id'],
                        ) != (
                            leg['route'].origin_id,
                            leg['route'].destination_id,
                        ) and leg['fare'] < record.total_estimated_fare:
                            partial_cheaper += 1
        self.assertGreater(checked, 0)
        self.assertGreater(
            partial_cheaper, 0,
            'a shorter origin/destination pair must recalculate the fare',
        )

    def test_unknown_fare_is_reported_never_faked(self):
        checked = 0
        for origin in self.locations:
            for destination in self.locations:
                if origin.pk == destination.pk:
                    continue
                for journey in find_journeys(
                    origin.pk, destination.pk,
                    origin=origin, destination=destination,
                    network=self.network, include_map=False,
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
            self.assertEqual(
                map_payload['total_time'], journey['total_time'],
                'the map label must read the same journey total',
            )
            for leg in map_payload['legs']:
                self.assertIn(leg['color'], LEG_COLORS)

    def test_destination_summaries_report_km_based_times(self):
        """Dropdown time comes from the same journeys as the results page.

        The fare/time annotation shown next to each destination suggestion
        is built from the same km-based journey totals; the quickest option
        is never slower than the fare-wise cheapest pick.
        """
        origin = self.locations[0]
        summaries = destination_summaries(origin.pk, origin=origin)
        reachable = [s for s in summaries if s['has_route']]
        self.assertTrue(reachable)
        for summary in reachable:
            self.assertGreaterEqual(summary['minutes'], 1)
            self.assertGreaterEqual(summary['fastest_minutes'], 1)
            self.assertLessEqual(
                summary['fastest_minutes'], summary['minutes'],
            )


class FareSynchronizationTests(TestCase):
    """The shared fare table is the single source for every commuter view."""

    databases = {'sakayguide'}

    @classmethod
    def setUpTestData(cls):
        cls.network = _load_network()

    def test_transport_options_use_the_latest_active_record(self):
        current = latest_active_fares(
            RouteFare.objects.filter(status=RouteFare.STATUS_ACTIVE),
        )
        options = transport_options()
        self.assertGreater(len(options), 0)
        for option in options:
            record = current.get((option['route_id'], 1))
            expected = record.total_estimated_fare if record else None
            self.assertEqual(option['fare'], expected)
            self.assertEqual(
                option['minutes'],
                travel_minutes(
                    option['distance_km'],
                    option['transport_name'],
                    fallback_minutes=option['minutes'],
                ),
                f"{option['route_code']}: card time must equal the "
                f"km-based estimate",
            )

    def test_expired_and_future_rows_are_ignored(self):
        today = timezone.localdate()
        active_today = RouteFare(
            status=RouteFare.STATUS_ACTIVE,
            effective_date=today,
            total_estimated_fare=Decimal('15.00'),
        )
        future = RouteFare(
            status=RouteFare.STATUS_ACTIVE,
            effective_date=today + timedelta(days=1),
            total_estimated_fare=Decimal('99.00'),
        )
        expired = RouteFare(
            status=RouteFare.STATUS_ACTIVE,
            effective_date=today - timedelta(days=10),
            expiry_date=today - timedelta(days=1),
            total_estimated_fare=Decimal('99.00'),
        )
        self.assertTrue(fare_is_current(active_today, today))
        self.assertFalse(fare_is_current(future, today))
        self.assertFalse(fare_is_current(expired, today))

    def test_fare_version_is_a_stable_fingerprint(self):
        first = fares_version()
        second = fares_version()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 16)
        self.assertTrue(first.isalnum())
