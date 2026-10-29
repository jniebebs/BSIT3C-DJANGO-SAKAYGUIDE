from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

SAMPLE_STATS = {
    'municipality': {'name': 'Kabankalan', 'province': 'Negros Occidental'},
    'active_routes': 3,
    'route_stops': 10,
    'active_locations': 5,
    'barangays': 4,
    'transfers': 2,
    'active_fares': 3,
    'commuters': 2,
    'saved_routes': 1,
    'searches': 12,
    'landmarks': 4,
    'inactive_locations': 1,
    'transport_types': 2,
    'routes': [],
    'transfer_list': [],
    'transport_breakdown': [
        {'name': 'Jeepney', 'count': 3, 'percent': 100},
    ],
    'recent_logs': [],
    'location_list': [],
    'search_activity': [
        {'date': '2026-10-23', 'label': 'Fri', 'full_label': 'Oct 23', 'count': 1},
        {'date': '2026-10-24', 'label': 'Sat', 'full_label': 'Oct 24', 'count': 0},
        {'date': '2026-10-25', 'label': 'Sun', 'full_label': 'Oct 25', 'count': 0},
        {'date': '2026-10-26', 'label': 'Mon', 'full_label': 'Oct 26', 'count': 2},
        {'date': '2026-10-27', 'label': 'Tue', 'full_label': 'Oct 27', 'count': 3},
        {'date': '2026-10-28', 'label': 'Wed', 'full_label': 'Oct 28', 'count': 0},
        {'date': '2026-10-29', 'label': 'Thu', 'full_label': 'Oct 29', 'count': 1},
    ],
    'search_week_total': 7,
    'search_previous_week_total': 3,
    'search_week_change': None,
    'busiest_day': {
        'date': '2026-10-27', 'label': 'Tue', 'full_label': 'Oct 27', 'count': 3,
    },
    'top_destinations': [
        {'name': 'Ceres Bus Terminal', 'count': 4, 'share': 33, 'bar': 100},
    ],
    'recent_searches': [
        {
            'user': 'Test Commuter',
            'origin': 'Public Terminal',
            'destination': 'CityMall Kabankalan',
            'searched_at': timezone.now(),
            'minutes': 10,
        },
    ],
    'fare_min': 8,
    'fare_max': 30,
    'fare_average': 15,
    'active_with_coords': 5,
    'coverage_percent': 100,
    'activity_this_week': 1,
}


class HomeViewTests(TestCase):
    @patch('apps.core.views._sakayguide_stats', return_value=SAMPLE_STATS)
    def test_home_renders_for_authenticated_user(self, stats_mock):
        user = get_user_model().objects.create_user(
            username='admin', password='secret1234',
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')
        self.assertContains(response, 'Search activity')
        self.assertContains(response, 'Popular destinations')
        self.assertContains(response, 'Quick actions')
        self.assertContains(response, 'Est. travel')
        self.assertContains(response, 'CityMall Kabankalan')
        stats_mock.assert_called_once_with()

    @patch('apps.core.views._sakayguide_stats', side_effect=OperationalError)
    def test_home_shows_database_error(self, stats_mock):
        user = get_user_model().objects.create_user(
            username='admin2', password='secret1234',
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Could not connect to the SakayGuide database')
        stats_mock.assert_called_once_with()

    def test_home_requires_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 302)


class RegisterAuditTests(TestCase):
    @patch('apps.core.views.log_account_creation')
    def test_registration_writes_account_creation_log(self, log_mock):
        response = self.client.post(reverse('register'), {
            'username': 'newcommuter',
            'first_name': 'New',
            'last_name': 'Commuter',
            'email': 'newcommuter@example.com',
            'password': 'Str0ng!Passw0rd',
            'confirm_password': 'Str0ng!Passw0rd',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

        user = get_user_model().objects.get(username='newcommuter')
        log_mock.assert_called_once()
        kwargs = log_mock.call_args.kwargs
        self.assertEqual(kwargs['actor'], user)
        self.assertEqual(kwargs['account'], user)
        self.assertEqual(kwargs['account_role'], 'commuter')
        self.assertIn('Self-registered commuter account', kwargs['description'])
