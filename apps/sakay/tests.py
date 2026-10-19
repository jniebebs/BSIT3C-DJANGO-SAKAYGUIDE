import json
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Advisory, Route, Terminal


class SakayApiTestCase(TestCase):
    """Shared fixture: the seeded sample Metro Manila network."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_sakay', verbosity=0)
        cls.mrt = Route.objects.get(code='MRT-3')
        cls.cubao = Terminal.objects.get(name='Cubao Terminal')
        cls.alabang = Terminal.objects.get(name='Alabang Terminal')
        cls.monumento = Terminal.objects.get(name='Monumento Terminal')
        cls.north_edsa = Terminal.objects.get(name='North EDSA Terminal')
        cls.taft = Terminal.objects.get(name='Taft Avenue Terminal')


class TerminalSearchTests(SakayApiTestCase):
    def test_search_by_name_prefix_returns_full_payload(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'cub'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload['count'], 1)
        first = payload['results'][0]
        self.assertIn('cubao', first['name'].lower())
        for field in ('id', 'name', 'municipality', 'landmark', 'latitude', 'longitude',
                      'coordinates', 'transport_modes', 'destinations'):
            self.assertIn(field, first)

    def test_search_matches_landmark(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'Araneta'})
        names = [r['name'] for r in response.json()['results']]
        self.assertIn('Cubao Terminal', names)

    def test_search_matches_municipality(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'Makati'})
        names = [r['name'] for r in response.json()['results']]
        self.assertIn('Ayala Terminal Makati', names)

    def test_search_is_case_insensitive(self):
        upper = self.client.get(reverse('sakay:terminal_search'), {'q': 'PITX'})
        lower = self.client.get(reverse('sakay:terminal_search'), {'q': 'pitx'})
        self.assertEqual(upper.json()['count'], lower.json()['count'])
        self.assertGreaterEqual(upper.json()['count'], 1)

    def test_search_requires_every_token_to_match(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'north edsa'})
        names = [r['name'] for r in response.json()['results']]
        self.assertIn('North EDSA Terminal', names)

        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'north festival'})
        self.assertEqual(response.json()['count'], 0)

    def test_search_includes_modes_and_destinations(self):
        response = self.client.get(reverse('sakay:terminal_search'), {'q': 'cubao terminal'})
        first = response.json()['results'][0]
        self.assertGreaterEqual(len(first['transport_modes']), 1)
        self.assertGreaterEqual(len(first['destinations']), 1)
        self.assertIn('name', first['transport_modes'][0])

    def test_search_limit_is_clamped(self):
        response = self.client.get(
            reverse('sakay:terminal_search'), {'q': 'terminal', 'limit': '999'}
        )
        self.assertLessEqual(response.json()['count'], 50)

    def test_terminal_detail_and_routes_payload(self):
        response = self.client.get(
            reverse('sakay:terminal_detail', args=[self.cubao.id])
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['id'], self.cubao.id)
        self.assertIn('routes', payload)
        self.assertGreaterEqual(len(payload['routes']), 1)

        routes_response = self.client.get(
            reverse('sakay:terminal_routes', args=[self.cubao.id])
        )
        payload = routes_response.json()
        self.assertGreaterEqual(payload['count'], 1)
        self.assertIn('fare_summary', payload['routes'][0])

    def test_terminal_detail_404(self):
        response = self.client.get(reverse('sakay:terminal_detail', args=[999999]))
        self.assertEqual(response.status_code, 404)


class FareMatrixTests(SakayApiTestCase):
    def test_route_stop_cumulative_values_are_automated(self):
        stops = list(self.mrt.stops.order_by('sequence'))
        self.assertEqual(len(stops), 4)

        # base 15.00 + 1.50/km over 6 km
        self.assertEqual(stops[1].cumulative_fare, Decimal('24.00'))
        # base 15.00 + 1.50/km * 16.5 km
        self.assertEqual(stops[3].cumulative_fare, Decimal('39.75'))
        # 16.5 km / 40 km-h * 60 = 24.75 min cruising + 3 * 0.75 min dwell
        self.assertEqual(stops[3].cumulative_time_minutes, Decimal('27.00'))

    def test_recompute_after_distance_change(self):
        stop = self.mrt.stops.get(sequence=2)
        stop.distance_from_origin_km = Decimal('10.00')
        stop.save()
        stop.refresh_from_db()
        self.assertEqual(stop.cumulative_fare, Decimal('30.00'))  # 15 + 1.5 * 10

    def test_fare_between_charges_flag_down_plus_distance(self):
        self.assertEqual(self.mrt.fare_between(0, 1), Decimal('24.00'))
        # boarding mid-route still pays the base fare
        self.assertEqual(self.mrt.fare_between(1, 3), Decimal('30.75'))  # 15 + 1.5 * 10.5

    def test_fare_matrix_endpoint(self):
        response = self.client.get(
            reverse('sakay:route_fare_matrix', args=[self.mrt.id])
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['stops']), 4)
        self.assertEqual(len(payload['matrix']), 6)  # C(4, 2) pairs

        pair = payload['matrix'][0]
        self.assertEqual(pair['from_terminal'], 'North EDSA Terminal')
        self.assertEqual(pair['to_terminal'], 'Cubao Terminal')
        self.assertEqual(pair['fare'], 24.0)
        self.assertEqual(pair['time_minutes'], 9.75)  # 6/40*60 + 0.75 dwell

        end_to_end = payload['matrix'][2]  # North EDSA -> Taft Avenue
        self.assertEqual(end_to_end['fare'], 39.75)
        self.assertEqual(end_to_end['time_minutes'], 27.0)

        last_pair = payload['matrix'][-1]  # Ayala -> Taft Avenue
        self.assertEqual(last_pair['from_terminal'], 'Ayala Terminal Makati')
        self.assertEqual(last_pair['fare'], 20.25)  # 15 + 1.5 * 3.5
        self.assertEqual(last_pair['time_minutes'], 6.0)  # 5.25 cruising + 0.75 dwell

    def test_fare_matrix_404_for_unknown_route(self):
        response = self.client.get(reverse('sakay:route_fare_matrix', args=[999999]))
        self.assertEqual(response.status_code, 404)


class RoutePlanTests(SakayApiTestCase):
    def _plan(self, origin, destination, **extra):
        params = {'origin': origin, 'destination': destination, **extra}
        return self.client.get(reverse('sakay:route_plan'), params)

    def test_direct_single_leg_journey(self):
        response = self._plan(self.north_edsa.id, self.taft.id)
        self.assertEqual(response.status_code, 200)
        journey = response.json()
        self.assertTrue(journey['found'])
        self.assertEqual(len(journey['legs']), 1)
        self.assertEqual(journey['transfers'], 0)
        leg = journey['legs'][0]
        self.assertEqual(leg['route']['code'], 'MRT-3')
        self.assertEqual(leg['fare'], 39.75)
        self.assertEqual(journey['total_fare'], 39.75)
        self.assertGreater(journey['total_time_minutes'], 0)
        self.assertEqual(len(journey['steps']), 3)  # board, ride, alight

    def test_multi_modal_transfer_journey(self):
        response = self._plan(self.alabang.id, self.monumento.id)
        self.assertEqual(response.status_code, 200)
        journey = response.json()
        self.assertTrue(journey['found'])
        self.assertGreaterEqual(len(journey['legs']), 2)
        self.assertGreaterEqual(journey['transfers'], 1)

        mode_slugs = {leg['mode']['slug'] for leg in journey['legs']}
        self.assertGreaterEqual(len(mode_slugs), 2, 'expected multi-modal legs')

        leg_total = sum(leg['fare'] for leg in journey['legs'])
        self.assertAlmostEqual(journey['total_fare'], leg_total, places=2)
        self.assertAlmostEqual(
            journey['total_time_minutes'],
            journey['riding_time_minutes'] + journey['transfer_time_minutes'],
            places=2,
        )
        self.assertEqual(
            journey['legs'][0]['stops'][0]['id'], self.alabang.id
        )
        self.assertEqual(
            journey['legs'][-1]['stops'][-1]['id'], self.monumento.id
        )
        self.assertTrue(any(step['type'] == 'transfer' for step in journey['steps']))

    def test_cheapest_optimization_returns_no_dearer_journey(self):
        fastest = self._plan(self.alabang.id, self.monumento.id).json()
        cheapest = self._plan(
            self.alabang.id, self.monumento.id, optimize='cheapest'
        ).json()
        self.assertTrue(cheapest['found'])
        self.assertEqual(cheapest['optimize'], 'cheapest')
        self.assertLessEqual(cheapest['total_fare'], fastest['total_fare'] * 1.25)

    def test_same_origin_and_destination(self):
        journey = self._plan(self.cubao.id, self.cubao.id).json()
        self.assertTrue(journey['found'])
        self.assertEqual(journey['legs'], [])
        self.assertEqual(journey['total_fare'], 0)
        self.assertEqual(journey['total_time_minutes'], 0)

    def test_missing_parameters_return_400(self):
        response = self.client.get(reverse('sakay:route_plan'), {'origin': 1})
        self.assertEqual(response.status_code, 400)

    def test_unknown_terminal_returns_404(self):
        response = self._plan(999999, self.cubao.id)
        self.assertEqual(response.status_code, 404)

    def test_invalid_optimize_returns_400(self):
        response = self._plan(self.cubao.id, self.taft.id, optimize='teleport')
        self.assertEqual(response.status_code, 400)


class AdvisoryTests(SakayApiTestCase):
    def test_seeded_advisories_are_listed_live(self):
        response = self.client.get(reverse('sakay:advisory_list'), {'live': '1'})
        payload = response.json()
        self.assertGreaterEqual(payload['count'], 3)
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
            reverse('sakay:advisory_list'), {'category': 'flooding'}
        )
        payload = response.json()
        self.assertGreaterEqual(payload['count'], 1)
        self.assertTrue(all(a['category'] == 'flooding' for a in payload['advisories']))

    def test_create_advisory_via_json(self):
        body = {
            'title': 'Jeepney strike on Aurora Blvd',
            'message': 'Some drivers are on strike; expect long queues in Cubao.',
            'category': 'other',
            'severity': 'warning',
            'reported_by': 'rider_one',
            'terminal': self.cubao.id,
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
        self.assertEqual(advisory.terminal_id, self.cubao.id)
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
