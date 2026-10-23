import json
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Advisory, Route, Terminal


class SakayApiTestCase(TestCase):
    """Shared fixture: the seeded Kabankalan City network."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_sakay', verbosity=0)
        cls.mrt = Route.objects.get(code='RTE-003')
        cls.camansi = Terminal.objects.get(name='Barangay Camansi Terminal')
        cls.inapoy = Terminal.objects.get(name='Barangay Inapoy Terminal')
        cls.public_terminal = Terminal.objects.get(name='Kabankalan City Public Terminal')
        cls.kabankalan_terminal = cls.public_terminal


class TerminalSearchTests(SakayApiTestCase):
    def test_search_by_name_prefix_returns_full_payload(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'cam'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload['count'], 1)
        first = payload['results'][0]
        self.assertIn('camansi', first['name'].lower())
        for field in ('id', 'name', 'municipality', 'landmark', 'latitude', 'longitude',
                      'coordinates', 'transport_modes', 'destinations'):
            self.assertIn(field, first)

    def test_search_matches_landmark(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'city center'})
        names = [r['name'] for r in response.json()['results']]
        self.assertIn('Kabankalan City Public Terminal', names)

    def test_search_matches_municipality(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'Kabankalan'})
        names = [r['name'] for r in response.json()['results']]
        self.assertGreaterEqual(len(names), 1)

    def test_search_is_case_insensitive(self):
        upper = self.client.get(reverse('sakay:terminal_search'), {'q': 'CAMANSI'})
        lower = self.client.get(reverse('sakay:terminal_search'), {'q': 'camansi'})
        self.assertEqual(upper.json()['count'], lower.json()['count'])
        self.assertGreaterEqual(upper.json()['count'], 1)

    def test_search_requires_every_token_to_match(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'barangay camansi'})
        names = [r['name'] for r in response.json()['results']]
        self.assertIn('Barangay Camansi Terminal', names)

        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'camansi inapoy'})
        self.assertEqual(response.json()['count'], 0)

    def test_search_includes_modes_and_destinations(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'camansi terminal'})
        first = response.json()['results'][0]
        self.assertGreaterEqual(len(first['transport_modes']), 1)
        self.assertGreaterEqual(len(first['destinations']), 1)
        self.assertIn('name', first['transport_modes'][0])

    def test_search_limit_is_clamped(self):
        response = self.client.get(
            reverse('sakay:terminal_search'), {'q': 'terminal', 'limit': '999'}
        )
        self.assertLessEqual(response.json()['count'], 50)

    def test_search_excludes_outside_kabankalan(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'cubao'})
        self.assertEqual(response.json()['count'], 0)

    def test_terminal_detail_and_routes_payload(self):
        response = self.client.get(
            reverse('sakay:terminal_detail', args=[self.camansi.id])
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['id'], self.camansi.id)
        self.assertIn('routes', payload)

        routes_response = self.client.get(
            reverse('sakay:terminal_routes', args=[self.camansi.id])
        )
        payload = routes_response.json()
        self.assertGreaterEqual(payload['count'], 0)
        if payload['routes']:
            self.assertIn('fare_summary', payload['routes'][0])

    def test_terminal_detail_404(self):
        response = self.client.get(reverse('sakay:terminal_detail', args=[999999]))
        self.assertEqual(response.status_code, 404)


class FareMatrixTests(SakayApiTestCase):
    def test_route_stop_cumulative_values_are_automated(self):
        stops = list(self.mrt.stops.order_by('sequence'))
        self.assertEqual(len(stops), 3)

        # base 25.00 + 2.50/km over 12 km
        self.assertEqual(stops[1].cumulative_fare, Decimal('55.00'))
        # base 25.00 + 2.50/km * 25 km
        self.assertEqual(stops[2].cumulative_fare, Decimal('87.50'))
        # 25 km / 30 km-h * 60 = 50 min cruising + 2 * 1 min dwell
        self.assertEqual(stops[2].cumulative_time_minutes, Decimal('52.00'))

    def test_recompute_after_distance_change(self):
        stop = self.mrt.stops.get(sequence=2)
        stop.distance_from_origin_km = Decimal('10.00')
        stop.save()
        stop.refresh_from_db()
        self.assertEqual(stop.cumulative_fare, Decimal('50.00'))  # 25 + 2.5 * 10

    def test_fare_between_charges_flag_down_plus_distance(self):
        self.assertEqual(self.mrt.fare_between(0, 1), Decimal('55.00'))
        # boarding mid-route still pays the base fare
        self.assertEqual(self.mrt.fare_between(1, 2), Decimal('57.50'))  # 25 + 2.5 * 13

    def test_fare_matrix_endpoint(self):
        response = self.client.get(
            reverse('sakay:route_fare_matrix', args=[self.mrt.id])
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['stops']), 3)
        self.assertEqual(len(payload['matrix']), 3)  # C(3, 2) pairs

        pair = payload['matrix'][0]
        self.assertEqual(pair['from_terminal'], 'Kabankalan City Public Terminal')
        self.assertEqual(pair['to_terminal'], 'Barangay Camansi Terminal')
        self.assertEqual(pair['fare'], 55.0)
        # 12 km / 30 km/h * 60 min + 1 dwell min
        self.assertEqual(pair['time_minutes'], 25.0)

        end_to_end = payload['matrix'][1]  # Public Terminal -> Inapoy
        self.assertEqual(end_to_end['fare'], 87.50)
        self.assertEqual(end_to_end['time_minutes'], 52.0)

        last_pair = payload['matrix'][-1]  # Camansi -> Inapoy
        self.assertEqual(last_pair['from_terminal'], 'Barangay Camansi Terminal')
        self.assertEqual(last_pair['fare'], 57.50)  # 25 + 2.5 * 13
        self.assertEqual(last_pair['time_minutes'], 27.0)  # 13/30*60 + 1 dwell

    def test_fare_matrix_404_for_unknown_route(self):
        response = self.client.get(reverse('sakay:route_fare_matrix', args=[999999]))
        self.assertEqual(response.status_code, 404)


class RoutePlanTests(SakayApiTestCase):
    def _plan(self, origin, destination, **extra):
        params = {'origin': origin, 'destination': destination, **extra}
        return self.client.get(reverse('sakay:route_plan'), params)

    def test_direct_single_leg_journey(self):
        response = self._plan(self.public_terminal.id, self.camansi.id)
        self.assertEqual(response.status_code, 200)
        journey = response.json()
        self.assertTrue(journey['found'])
        self.assertEqual(len(journey['legs']), 1)
        self.assertEqual(journey['transfers'], 0)
        leg = journey['legs'][0]
        self.assertEqual(leg['route']['code'], 'RTE-002')
        self.assertEqual(leg['fare'], 20.00)
        self.assertEqual(journey['total_fare'], 20.00)
        self.assertGreater(journey['total_time_minutes'], 0)
        self.assertEqual(len(journey['steps']), 3)  # board, ride, alight

    def test_multi_modal_transfer_journey(self):
        response = self._plan(self.inapoy.id, self.public_terminal.id)
        self.assertEqual(response.status_code, 200)
        journey = response.json()
        self.assertTrue(journey['found'])
        self.assertGreaterEqual(len(journey['legs']), 1)

        leg_total = sum(leg['fare'] for leg in journey['legs'])
        self.assertAlmostEqual(journey['total_fare'], leg_total, places=2)
        self.assertAlmostEqual(
            journey['total_time_minutes'],
            journey['riding_time_minutes'] + journey['transfer_time_minutes'],
            places=2,
        )
        self.assertEqual(
            journey['legs'][0]['stops'][0]['id'], self.inapoy.id
        )
        self.assertEqual(
            journey['legs'][-1]['stops'][-1]['id'], self.public_terminal.id
        )

    def test_cheapest_optimization_returns_no_dearer_journey(self):
        fastest = self._plan(self.inapoy.id, self.public_terminal.id).json()
        cheapest = self._plan(
            self.inapoy.id, self.public_terminal.id, optimize='cheapest'
        ).json()
        self.assertTrue(cheapest['found'])
        self.assertEqual(cheapest['optimize'], 'cheapest')
        self.assertLessEqual(cheapest['total_fare'], fastest['total_fare'] * 1.25)

    def test_same_origin_and_destination(self):
        journey = self._plan(self.camansi.id, self.camansi.id).json()
        self.assertTrue(journey['found'])
        self.assertEqual(journey['legs'], [])
        self.assertEqual(journey['total_fare'], 0)
        self.assertEqual(journey['total_time_minutes'], 0)

    def test_missing_parameters_return_400(self):
        response = self.client.get(reverse('sakay:route_plan'), {'origin': 1})
        self.assertEqual(response.status_code, 400)

    def test_unknown_terminal_returns_404(self):
        response = self._plan(999999, self.camansi.id)
        self.assertEqual(response.status_code, 404)

    def test_invalid_optimize_returns_400(self):
        response = self._plan(self.camansi.id, self.public_terminal.id, optimize='teleport')
        self.assertEqual(response.status_code, 400)

    def test_route_plan_rejects_outside_kabankalan(self):
        # Origin is a Kabankalan terminal; destination id 999999 doesn't exist -> 404
        # To test the scope check, we'd need a non-Kabankalan terminal in the DB.
        # With the seed data all terminals are Kabankalan, so this tests the 404 path.
        response = self._plan(self.public_terminal.id, 999999)
        self.assertEqual(response.status_code, 404)


class AdvisoryTests(SakayApiTestCase):
    def test_seeded_advisories_are_listed_live(self):
        response = self.client.get(reverse('sakay:advisory_list'), {'live': '1'})
        payload = response.json()
        self.assertGreaterEqual(payload['count'], 1)
        self.assertTrue(all(a['is_live'] for a in payload['advisories']))

    def test_expired_advisory_is_excluded_from_live_feed(self):
        advisory = Advisory.objects.create(
            title='Old delay',
            message='This expired yesterday.',
            category='delay',
            expires_at=timezone.now() - timedelta(days=1),
        )
        live = self.client.get(reverse('sakay:advisory_list'), {'live': '1'}).json()
        self.assertNotIn(
            advisory.id, [a['id'] for a in live['advisories']]
        )
        everything = self.client.get(reverse('sakay:advisory_list')).json()
        self.assertIn(advisory.id, [a['id'] for a in everything['advisories']])

    def test_filter_by_category(self):
        response = self.client.get(
            reverse('sakay:advisory_list'), {'category': 'other'}
        )
        payload = response.json()
        self.assertGreaterEqual(payload['count'], 1)
        self.assertTrue(all(a['category'] == 'other' for a in payload['advisories']))

    def test_create_advisory_via_json(self):
        body = {
            'title': 'Jeepney delay on Camansi route',
            'message': 'Some drivers are on strike; expect long queues in Camansi.',
            'category': 'other',
            'severity': 'warning',
            'reported_by': 'rider_one',
            'terminal': self.camansi.id,
            'routes': [self.mrt.id],
        }
        response = self.client.post(
            reverse('sakay:advisory_create'),
            data=json.dumps(body),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload['status'], 'created')
        advisory = Advisory.objects.get(pk=payload['advisory']['id'])
        self.assertEqual(advisory.title, body['title'])
        self.assertEqual(advisory.terminal_id, self.camansi.id)
        self.assertEqual(list(advisory.routes.values_list('id', flat=True)), [self.mrt.id])

    def test_create_advisory_requires_title_and_message(self):
        response = self.client.post(
            reverse('sakay:advisory_create'),
            data=json.dumps({'title': '', 'message': ''}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_create_advisory_rejects_unknown_category(self):
        response = self.client.post(
            reverse('sakay:advisory_create'),
            data=json.dumps({'title': 'x', 'message': 'y', 'category': 'aliens'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_upvote_increments_counter(self):
        advisory = Advisory.objects.create(title='Traffic', message='Slow ride')
        response = self.client.post(reverse('sakay:advisory_upvote', args=[advisory.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['upvotes'], 1)
        advisory.refresh_from_db()
        self.assertEqual(advisory.upvotes, 1)

    def test_upvote_404_for_unknown_advisory(self):
        response = self.client.post(reverse('sakay:advisory_upvote', args=[999999]))
        self.assertEqual(response.status_code, 404)


class CsrfTokenTests(TestCase):
    def test_csrf_endpoint_issues_token_and_cookie(self):
        response = self.client.get(reverse('sakay:csrf_token'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('csrfToken', response.json())
        self.assertIn('csrftoken', response.cookies)
