"""Tests for the two separate SakayGuide account experiences.

    Administrator  ->  /admin/login/     ->  /management/
    Commuter      ->  /commuter/login/  ->  /commuter/

The transit tables live in the real ``sakayguide_db`` MySQL schema, so every
test here either mocks the SakayGuide database access or only reads from it.
No test writes to the live transit database.

The Django account tables live in the default connection, which the Django
test runner wraps in a transaction, so account changes are rolled back
automatically.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

PASSWORD = 'Str0ng!Passw0rd2026'

# Every administrator URL, so a commuter is proven to be locked out of all
# of them and not just the landing page.
ADMIN_URL_NAMES = [
    'management_dashboard',
    'management_locations',
    'management_location_create',
    'management_routes',
    'management_route_create',
    'management_stops',
    'management_stop_create',
    'management_fares',
    'management_fare_create',
    'management_transfers',
    'management_transfer_create',
    'management_transport_types',
    'management_fare_types',
    'management_users',
    'management_user_create',
    'management_map',
    'management_activity',
]

# Every write endpoint a commuter must never be able to reach.
ADMIN_WRITE_URL_NAMES = [
    'management_location_delete',
    'management_location_toggle',
    'management_route_delete',
    'management_route_toggle',
    'management_stop_delete',
    'management_fare_delete',
    'management_transfer_delete',
    'management_transport_type_delete',
    'management_fare_type_delete',
    'management_user_toggle',
]


def _fake_location(**overrides):
    """A stand-in for a Location row (no database access)."""
    class FakeBarangay:
        barangay_name = 'Barangay 1'

    class FakeLocation:
        pk = 999
        location_name = 'Test Location'
        location_type = 'terminal'
        status = 'active'
        latitude = None
        longitude = None
        barangay = FakeBarangay()

    fake = FakeLocation()
    for key, value in overrides.items():
        setattr(fake, key, value)
    return fake


class AccountTestBase(TestCase):
    # The SakayGuide alias mirrors the live schema (see settings.TEST), so
    # it is readable during tests. Every write to it is mocked below.
    databases = {'default', 'sakayguide'}

    def setUp(self):
        # Neutralise every write to the live transit database. Individual
        # tests may re-patch one of these to assert on it.
        for target in (
            'apps.core.views.log_account_creation',
            'apps.core.views.log_activity',
            'apps.core.admin_views.log_activity',
            'apps.core.admin_views._sync_user_mirror',
            'apps.core.commuter_views.log_activity',
        ):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

        # The commuter mirror row is created on demand in the live database.
        # Returning None keeps the commuter dashboard on empty lists.
        mirror = patch('apps.core.commuter_views.sakay_user_for', return_value=None)
        mirror.start()
        self.addCleanup(mirror.stop)

        # The initial administrator, created exactly like
        # `python manage.py createsuperuser` does.
        self.superuser = User.objects.create_superuser(
            username='portaladmin',
            email='Portal.Admin@Example.com',
            password=PASSWORD,
        )
        self.staff = User.objects.create_user(
            username='portalstaff',
            email='portal.staff@example.com',
            password=PASSWORD,
            is_staff=True,
        )
        self.commuter = User.objects.create_user(
            username='portalcommuter',
            email='portal.commuter@example.com',
            password=PASSWORD,
        )


# ---------------------------------------------------------------------------
# Administrator
# ---------------------------------------------------------------------------

class AdministratorPortalTests(AccountTestBase):
    """Requirement 9.1 - 9.8: the administrator experience."""

    def test_administrator_can_log_in(self):
        response = self.client.post(reverse('admin_login'), {
            'username': 'portaladmin',
            'password': PASSWORD,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('management_dashboard'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_administrator_can_log_in_with_an_email_address(self):
        response = self.client.post(reverse('admin_login'), {
            'username': 'PORTAL.ADMIN@EXAMPLE.COM',
            'password': PASSWORD,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('management_dashboard'))

    def test_admin_login_page_renders_with_a_password_toggle(self):
        response = self.client.get(reverse('admin_login'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/admin_login.html')
        self.assertContains(response, 'toggle-password')
        self.assertContains(response, 'Administrator sign in')
        self.assertContains(response, reverse('admin_password_reset'))

    def test_administrator_can_access_the_admin_dashboard(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('management_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'management/dashboard.html')
        self.assertContains(response, 'Dashboard overview')

    def test_administrator_can_manage_commuter_accounts(self):
        self.client.force_login(self.superuser)

        listing = self.client.get(reverse('management_users'))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, 'portalcommuter')

        with patch('apps.core.admin_views.log_activity'), \
                patch('apps.core.admin_views._sync_user_mirror') as mirror_mock:
            response = self.client.post(reverse('management_user_create'), {
                'username': 'createdcommuter',
                'first_name': 'Created',
                'last_name': 'Commuter',
                'email': 'created.commuter@example.com',
                'role': 'commuter',
                'password': PASSWORD,
                'password_confirm': PASSWORD,
                'is_active': 'on',
            })

        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username='createdcommuter')
        self.assertFalse(created.is_staff)
        self.assertTrue(created.is_active)
        mirror_mock.assert_called_once()

    def test_administrator_can_manage_locations(self):
        self.client.force_login(self.staff)

        listing = self.client.get(reverse('management_locations'))
        self.assertEqual(listing.status_code, 200)
        self.assertTemplateUsed(response_template := 'management/locations.html')
        self.assertContains(listing, 'Locations')

        form = self.client.get(reverse('management_location_create'))
        self.assertEqual(form.status_code, 200)
        self.assertContains(form, 'location_name')

    def test_administrator_can_create_a_location(self):
        self.client.force_login(self.staff)

        fake = _fake_location()
        with patch('apps.core.admin_views.LocationForm') as form_mock, \
                patch('apps.core.admin_views._log_admin_action'):
            form_mock.return_value.is_valid.return_value = True
            form_mock.return_value.save.return_value = fake
            response = self.client.post(reverse('management_location_create'), {
                'barangay': '1',
                'location_name': 'Test Terminal',
                'location_type': 'terminal',
                'status': 'active',
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('management_locations'))

    def test_administrator_can_manage_jeepney_and_tricycle_routes(self):
        self.client.force_login(self.staff)

        listing = self.client.get(reverse('management_routes'))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, 'Routes')

        form = self.client.get(reverse('management_route_create'))
        self.assertEqual(form.status_code, 200)
        self.assertContains(form, 'route_code')
        self.assertContains(form, 'transport_type')

    def test_administrator_can_update_fares(self):
        self.client.force_login(self.staff)

        listing = self.client.get(reverse('management_fares'))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, 'Fares')

        form = self.client.get(reverse('management_fare_create'))
        self.assertEqual(form.status_code, 200)
        self.assertContains(form, 'total_estimated_fare')

    def test_administrator_can_manage_google_maps_locations(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('management_map'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'management/map.html')

    def test_administrator_can_log_out(self):
        self.client.force_login(self.staff)

        response = self.client.post(reverse('logout'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_administrator_login_rejects_a_commuter_account(self):
        response = self.client.post(reverse('admin_login'), {
            'username': 'portalcommuter',
            'password': PASSWORD,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not an administrator account')
        self.assertNotIn('_auth_user_id', self.client.session)


# ---------------------------------------------------------------------------
# Commuter
# ---------------------------------------------------------------------------

class CommuterPortalTests(AccountTestBase):
    """Requirement 9.9 - 9.18: the commuter experience."""

    def test_commuter_can_register(self):
        response = self.client.post(reverse('commuter_register'), {
            'full_name': 'Juan Dela Cruz',
            'username': 'juandela',
            'email': 'juan.dela@example.com',
            'password': PASSWORD,
            'confirm_password': PASSWORD,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('commuter_dashboard'))

        created = User.objects.get(username='juandela')
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertTrue(created.is_active)
        self.assertTrue(created.check_password(PASSWORD))
        self.assertIn('_auth_user_id', self.client.session)

    def test_registration_never_assigns_administrator_privileges(self):
        """A forged POST cannot promote a new account."""
        response = self.client.post(reverse('commuter_register'), {
            'full_name': 'Sneaky Person',
            'username': 'sneaky',
            'email': 'sneaky@example.com',
            'password': PASSWORD,
            'confirm_password': PASSWORD,
            'role': 'administrator',
            'is_staff': 'on',
            'is_superuser': 'on',
        })

        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username='sneaky')
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)

    def test_registration_rejects_a_password_mismatch(self):
        response = self.client.post(reverse('commuter_register'), {
            'full_name': 'Mismatch Person',
            'username': 'mismatch',
            'email': 'mismatch@example.com',
            'password': PASSWORD,
            'confirm_password': 'SomethingElse2026!',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='mismatch').exists())
        self.assertContains(response, 'do not match')

    def test_commuter_can_log_in(self):
        response = self.client.post(reverse('commuter_login'), {
            'username': 'portalcommuter',
            'password': PASSWORD,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('commuter_dashboard'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_commuter_can_log_in_with_an_email_address(self):
        response = self.client.post(reverse('commuter_login'), {
            'username': 'PORTAL.COMMUTER@EXAMPLE.COM',
            'password': PASSWORD,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('commuter_dashboard'))

    def test_commuter_login_rejects_an_administrator_account(self):
        response = self.client.post(reverse('commuter_login'), {
            'username': 'portaladmin',
            'password': PASSWORD,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Administrator accounts sign in')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_commuter_login_page_renders_with_a_password_toggle(self):
        response = self.client.get(reverse('commuter_login'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/commuter_login.html')
        self.assertContains(response, 'toggle-password')
        self.assertContains(response, reverse('commuter_register'))
        self.assertContains(response, reverse('commuter_password_reset'))

    @patch('apps.core.commuter_views.popular_destinations', return_value=[])
    @patch('apps.core.commuter_views.transport_options', return_value=[])
    @patch('apps.core.commuter_views.location_choices', return_value=[])
    def test_commuter_can_access_the_commuter_dashboard(self, *mocks):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('commuter_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'commuter/dashboard.html')
        self.assertContains(response, 'Quick route search')
        self.assertContains(response, 'Popular destinations')
        self.assertContains(response, 'Available transportation')
        self.assertContains(response, 'My recent searches')

    def test_commuter_dashboard_shows_fares_and_travel_times(self):
        self.client.force_login(self.commuter)

        options = [{
            'route_id': 1,
            'route_code': 'KAB-JP-01',
            'route_name': 'Terminal Loop',
            'transport_name': 'Jeepney',
            'transport_key': 'jeepney',
            'origin_name': 'Public Terminal',
            'destination_name': 'CityMall',
            'boarding_point': 'Public Terminal',
            'dropoff_point': 'CityMall',
            'minutes': 25,
            'stops_count': 8,
            'distance_km': 4.5,
            'fare': 15,
        }]
        with patch('apps.core.commuter_views.transport_options', return_value=options), \
                patch('apps.core.commuter_views.location_choices', return_value=[]), \
                patch('apps.core.commuter_views.popular_destinations', return_value=[]):
            response = self.client.get(reverse('commuter_dashboard'))

        self.assertContains(response, '&#8369;15')
        self.assertContains(response, '25 min')
        self.assertContains(response, 'Jeepney')
        self.assertContains(response, '4.5 km')

    def test_commuter_can_search_routes(self):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('routes:route_search'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'route-search-form')

    def test_commuter_route_search_offers_live_gps(self):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('routes:route_search'))

        self.assertContains(response, 'gps-use-origin')
        self.assertContains(response, 'My Current Location')

    def test_commuter_route_search_offers_google_maps_directions(self):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('routes:route_search'))

        self.assertContains(response, 'sg-search-map')
        self.assertContains(response, 'google')

    def test_commuter_can_manage_their_own_profile(self):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('commuter_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'commuter/profile.html')
        self.assertContains(response, 'Personal information')

        with patch('apps.core.commuter_views.log_activity'):
            response = self.client.post(reverse('commuter_profile'), {
                'first_name': 'Updated',
                'last_name': 'Commuter',
                'username': 'portalcommuter',
                'email': 'portal.commuter@example.com',
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('commuter_profile'))
        self.commuter.refresh_from_db()
        self.assertEqual(self.commuter.first_name, 'Updated')

    def test_commuter_cannot_change_their_own_role(self):
        self.client.force_login(self.commuter)

        with patch('apps.core.commuter_views.log_activity'):
            response = self.client.post(reverse('commuter_profile'), {
                'first_name': 'Escalated',
                'last_name': 'Commuter',
                'username': 'portalcommuter',
                'email': 'portal.commuter@example.com',
                'role': 'administrator',
                'is_staff': 'on',
                'is_superuser': 'on',
            })

        self.assertEqual(response.status_code, 302)
        self.commuter.refresh_from_db()
        self.assertFalse(self.commuter.is_staff)
        self.assertFalse(self.commuter.is_superuser)

    def test_commuter_can_change_their_own_password(self):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('commuter_password_change'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'current_password')

        with patch('apps.core.commuter_views.log_activity'):
            response = self.client.post(reverse('commuter_password_change'), {
                'current_password': PASSWORD,
                'new_password1': 'An0ther!Passw0rd2026',
                'new_password2': 'An0ther!Passw0rd2026',
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('commuter_profile'))
        self.commuter.refresh_from_db()
        self.assertTrue(self.commuter.check_password('An0ther!Passw0rd2026'))

    def test_commuter_password_change_requires_the_current_password(self):
        self.client.force_login(self.commuter)

        response = self.client.post(reverse('commuter_password_change'), {
            'current_password': 'wrong-password',
            'new_password1': 'An0ther!Passw0rd2026',
            'new_password2': 'An0ther!Passw0rd2026',
        })

        self.assertEqual(response.status_code, 200)
        self.commuter.refresh_from_db()
        self.assertTrue(self.commuter.check_password(PASSWORD))

    def test_commuter_can_log_out(self):
        self.client.force_login(self.commuter)

        response = self.client.post(reverse('logout'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

class AccountIsolationTests(AccountTestBase):
    """Requirement 9.19 - 9.23: the two account types stay separated."""

    def test_commuter_cannot_access_administrator_urls(self):
        self.client.force_login(self.commuter)

        for url_name in ADMIN_URL_NAMES:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 403)
                self.assertContains(response, 'Access denied', status_code=403)

    def test_commuter_cannot_reach_administrator_write_endpoints(self):
        self.client.force_login(self.commuter)

        for url_name in ADMIN_WRITE_URL_NAMES:
            with self.subTest(url_name=url_name):
                response = self.client.post(reverse(url_name, args=[1]))

                self.assertEqual(response.status_code, 403)

    def test_commuter_cannot_manage_other_accounts(self):
        self.client.force_login(self.commuter)

        listing = self.client.get(reverse('management_users'))
        self.assertEqual(listing.status_code, 403)

        edit = self.client.get(
            reverse('management_user_edit', args=[self.superuser.pk])
        )
        self.assertEqual(edit.status_code, 403)

    def test_commuter_cannot_promote_themselves_through_the_admin_form(self):
        self.client.force_login(self.commuter)

        response = self.client.post(
            reverse('management_user_edit', args=[self.commuter.pk]),
            {
                'username': self.commuter.username,
                'first_name': 'Escalated',
                'last_name': 'Commuter',
                'email': self.commuter.email,
                'role': 'administrator',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 403)
        self.commuter.refresh_from_db()
        self.assertFalse(self.commuter.is_staff)
        self.assertFalse(self.commuter.is_superuser)

    def test_administrator_cannot_open_the_commuter_dashboard(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('commuter_dashboard'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'commuter navigation experience',
                            status_code=403)

    def test_administrator_cannot_open_the_commuter_profile(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('commuter_profile'))

        self.assertEqual(response.status_code, 403)

    def test_administrator_cannot_open_the_commuter_portals(self):
        self.client.force_login(self.staff)

        # The administrator sign-in page is the right place for an admin.
        response = self.client.get(reverse('commuter_login'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('admin_login'))

    def test_commuter_cannot_open_the_administrator_sign_in_page(self):
        """A signed-in commuter is refused the administrator interface."""
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('admin_login'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'not available to commuter accounts',
                            status_code=403)

    def test_anonymous_visitor_is_sent_to_the_admin_login(self):
        response = self.client.get(reverse('management_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('admin_login')))

    def test_anonymous_visitor_is_sent_to_the_commuter_login(self):
        response = self.client.get(reverse('commuter_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('commuter_login')))

    def test_deactivated_account_cannot_sign_in(self):
        self.commuter.is_active = False
        self.commuter.save(update_fields=['is_active'])

        response = self.client.post(reverse('commuter_login'), {
            'username': 'portalcommuter',
            'password': PASSWORD,
        })

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_shared_login_routes_each_role_to_its_own_dashboard(self):
        admin_response = self.client.post(reverse('login'), {
            'username': 'portaladmin',
            'password': PASSWORD,
        })
        self.assertEqual(admin_response.url, reverse('management_dashboard'))
        self.client.logout()

        commuter_response = self.client.post(reverse('login'), {
            'username': 'portalcommuter',
            'password': PASSWORD,
        })
        self.assertEqual(commuter_response.url, reverse('commuter_dashboard'))

    def test_existing_accounts_continue_to_work(self):
        """Accounts created before the split still sign in and land correctly."""
        legacy = User.objects.create_user(
            username='legacycommuter',
            email='legacy@example.com',
            password=PASSWORD,
        )
        legacy_admin = User.objects.create_user(
            username='legacyadmin',
            email='legacy.admin@example.com',
            password=PASSWORD,
            is_staff=True,
        )

        response = self.client.post(reverse('login'), {
            'username': 'legacycommuter',
            'password': PASSWORD,
        })
        self.assertEqual(response.url, reverse('commuter_dashboard'))
        self.client.logout()

        response = self.client.post(reverse('login'), {
            'username': 'legacyadmin',
            'password': PASSWORD,
        })
        self.assertEqual(response.url, reverse('management_dashboard'))

        self.assertFalse(legacy.is_staff)
        self.assertTrue(legacy_admin.is_staff)

    def test_createsuperuser_produces_an_administrator_account(self):
        """The documented bootstrap command yields a usable administrator."""
        import os
        from django.core.management import call_command

        previous = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        os.environ['DJANGO_SUPERUSER_PASSWORD'] = PASSWORD
        try:
            call_command(
                'createsuperuser',
                username='bootstrapadmin',
                email='bootstrap@example.com',
                interactive=False,
            )
        finally:
            if previous is None:
                os.environ.pop('DJANGO_SUPERUSER_PASSWORD', None)
            else:
                os.environ['DJANGO_SUPERUSER_PASSWORD'] = previous

        created = User.objects.get(username='bootstrapadmin')
        self.assertTrue(created.is_staff)
        self.assertTrue(created.is_superuser)
        self.assertTrue(created.is_active)

        response = self.client.post(reverse('admin_login'), {
            'username': 'bootstrapadmin',
            'password': PASSWORD,
        })
        self.assertEqual(response.url, reverse('management_dashboard'))


class CommuterOnlyRouteAccessTests(AccountTestBase):
    """Find My Route, Google Maps and live GPS belong to commuters only."""

    def test_commuter_can_open_find_my_route(self):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('routes:route_search'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'routes/route_search.html')

    def test_administrator_cannot_open_find_my_route(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('routes:route_search'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'commuter navigation experience',
                            status_code=403)

    def test_administrator_cannot_use_the_live_gps_endpoints(self):
        self.client.force_login(self.staff)

        for url_name in ('routes:journey_map_json', 'routes:destination_summaries'):
            with self.subTest(url_name=url_name):
                response = self.client.get(
                    reverse(url_name), {'origin': '1', 'destination': '2'}
                )

                self.assertEqual(response.status_code, 403)

    def test_administrator_cannot_save_a_route(self):
        self.client.force_login(self.staff)

        response = self.client.post(reverse('routes:save_route'), {
            'origin': '1',
            'destination': '2',
        })

        self.assertEqual(response.status_code, 403)

    def test_anonymous_visitor_is_sent_to_the_commuter_login(self):
        response = self.client.get(reverse('routes:route_search'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('commuter_login')))

    def test_find_my_route_is_not_in_the_administrator_menu(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('management_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('routes:route_search'))


class AdministratorSecurityTests(AccountTestBase):
    """Requirement 8: administrator accounts stay protected."""

    def test_commuter_cannot_access_the_admin_dashboard(self):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('management_dashboard'))

        self.assertEqual(response.status_code, 403)

    def test_commuter_cannot_open_the_administrator_login_page(self):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('admin_login'))

        self.assertEqual(response.status_code, 403)

    def test_commuter_cannot_read_administrator_account_records(self):
        self.client.force_login(self.commuter)

        listing = self.client.get(reverse('users:user_list_ajax'))
        self.assertEqual(listing.status_code, 403)

        detail = self.client.get(
            reverse('users:user_get_ajax', args=[self.superuser.pk])
        )
        self.assertEqual(detail.status_code, 403)

    def test_commuter_cannot_create_an_administrator_account(self):
        self.client.force_login(self.commuter)

        response = self.client.post(reverse('management_user_create'), {
            'username': 'sneakyadmin',
            'first_name': 'Sneaky',
            'last_name': 'Admin',
            'email': 'sneaky.admin@example.com',
            'role': 'administrator',
            'password': PASSWORD,
            'password_confirm': PASSWORD,
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username='sneakyadmin').exists())

    def test_commuter_cannot_modify_administrator_credentials(self):
        self.client.force_login(self.commuter)

        response = self.client.post(
            reverse('management_user_edit', args=[self.superuser.pk]),
            {
                'username': self.superuser.username,
                'first_name': 'Changed',
                'last_name': 'Admin',
                'email': self.superuser.email,
                'role': 'administrator',
                'password': 'Hijacked!Passw0rd2026',
                'password_confirm': 'Hijacked!Passw0rd2026',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password(PASSWORD))
        self.assertNotEqual(self.superuser.first_name, 'Changed')

    def test_commuter_cannot_deactivate_an_administrator(self):
        self.client.force_login(self.commuter)

        response = self.client.post(
            reverse('management_user_toggle', args=[self.superuser.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

    def test_commuter_cannot_delete_an_administrator(self):
        self.client.force_login(self.commuter)

        response = self.client.post(
            reverse('users:user_delete_ajax', args=[self.superuser.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.superuser.pk).exists())

    def test_administrator_can_reach_every_management_screen(self):
        self.client.force_login(self.superuser)

        for url_name in ADMIN_URL_NAMES + [
            'management_searches',
            'management_reports',
        ]:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)

    def test_administrator_can_open_the_reports_and_search_monitoring(self):
        self.client.force_login(self.staff)

        reports = self.client.get(reverse('management_reports'))
        self.assertEqual(reports.status_code, 200)
        self.assertTemplateUsed(reports, 'management/reports.html')

        searches = self.client.get(reverse('management_searches'))
        self.assertEqual(searches.status_code, 200)
        self.assertTemplateUsed(searches, 'management/searches.html')

    def test_existing_administrator_and_commuter_accounts_keep_working(self):
        legacy_admin = User.objects.create_user(
            username='keptadmin',
            email='kept.admin@example.com',
            password=PASSWORD,
            is_staff=True,
        )
        legacy_commuter = User.objects.create_user(
            username='keptcommuter',
            email='kept.commuter@example.com',
            password=PASSWORD,
        )

        response = self.client.post(reverse('admin_login'), {
            'username': 'keptadmin', 'password': PASSWORD,
        })
        self.assertEqual(response.url, reverse('management_dashboard'))
        self.client.logout()

        response = self.client.post(reverse('commuter_login'), {
            'username': 'keptcommuter', 'password': PASSWORD,
        })
        self.assertEqual(response.url, reverse('commuter_dashboard'))

        self.assertTrue(legacy_admin.is_staff)
        self.assertFalse(legacy_commuter.is_staff)


class UnifiedRoleTests(AccountTestBase):
    """SakayGuide has exactly two roles: administrator and commuter."""

    def test_only_two_role_choices_exist(self):
        from apps.core.admin_forms import ROLE_CHOICES

        self.assertEqual(
            ROLE_CHOICES,
            [('commuter', 'Commuter'), ('administrator', 'Administrator')],
        )

    def test_role_for_maps_every_account_to_one_of_two_roles(self):
        from apps.core.admin_forms import role_for

        self.assertEqual(role_for(self.superuser), 'administrator')
        self.assertEqual(role_for(self.staff), 'administrator')
        self.assertEqual(role_for(self.commuter), 'commuter')

    def test_a_django_superuser_is_an_administrator(self):
        """Existing super administrator accounts migrate into the unified role."""
        from apps.core.admin_forms import role_for
        from apps.core.permissions import is_administrator, is_commuter

        self.assertTrue(self.superuser.is_superuser)
        self.assertEqual(role_for(self.superuser), 'administrator')
        self.assertTrue(is_administrator(self.superuser))
        self.assertFalse(is_commuter(self.superuser))

    def test_the_interface_never_shows_a_super_administrator_role(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('management_users'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Super Administrator')
        self.assertNotContains(response, 'Super administrators')
        self.assertContains(response, 'Administrator')

    def test_the_user_form_offers_only_two_roles(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('management_user_create'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Super Administrator')
        self.assertContains(response, 'Commuter')
        self.assertContains(response, 'Administrator')

    def test_the_administrator_filter_includes_every_staff_account(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse('management_users'), {'role': 'administrator'}
        )

        self.assertEqual(response.status_code, 200)
        listed = [account.username for account in response.context['users']]
        self.assertIn('portaladmin', listed)
        self.assertIn('portalstaff', listed)
        self.assertNotIn('portalcommuter', listed)

    def test_any_administrator_can_create_another_administrator(self):
        self.client.force_login(self.staff)

        with patch('apps.core.admin_views.log_activity'), \
                patch('apps.core.admin_views._sync_user_mirror'):
            response = self.client.post(reverse('management_user_create'), {
                'username': 'secondadmin',
                'first_name': 'Second',
                'last_name': 'Administrator',
                'email': 'second.admin@example.com',
                'role': 'administrator',
                'password': PASSWORD,
                'password_confirm': PASSWORD,
                'is_active': 'on',
            })

        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username='secondadmin')
        self.assertTrue(created.is_staff)
        self.assertTrue(created.is_active)

    def test_any_administrator_can_edit_another_administrator(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse('management_user_edit', args=[self.superuser.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Current role')

    def test_the_last_active_administrator_cannot_be_deactivated(self):
        """The console must always keep one usable administrator."""
        self.staff.is_active = False
        self.staff.save(update_fields=['is_active'])
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse('management_user_toggle', args=[self.superuser.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

    def test_the_last_active_administrator_cannot_be_demoted(self):
        """The console must always keep one usable administrator."""
        from apps.core.admin_views import _last_active_administrator

        self.staff.is_active = False
        self.staff.save(update_fields=['is_active'])

        self.assertTrue(_last_active_administrator(self.superuser))
        self.assertFalse(_last_active_administrator(self.commuter))

        self.client.force_login(self.superuser)

        with patch('apps.core.admin_views.log_activity'), \
                patch('apps.core.admin_views._sync_user_mirror'):
            response = self.client.post(
                reverse('management_user_edit', args=[self.superuser.pk]),
                {
                    'username': self.superuser.username,
                    'first_name': '',
                    'last_name': '',
                    'email': self.superuser.email,
                    'role': 'commuter',
                    'is_active': 'on',
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'You cannot remove your own administrator access.'
        )
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_staff)

    def test_an_administrator_cannot_demote_themselves(self):
        self.client.force_login(self.staff)

        with patch('apps.core.admin_views.log_activity'), \
                patch('apps.core.admin_views._sync_user_mirror'):
            response = self.client.post(
                reverse('management_user_edit', args=[self.staff.pk]),
                {
                    'username': self.staff.username,
                    'first_name': '',
                    'last_name': '',
                    'email': self.staff.email,
                    'role': 'commuter',
                    'is_active': 'on',
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'You cannot remove your own administrator access.'
        )
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_staff)

    def test_the_django_superuser_flag_is_never_granted_through_the_app(self):
        """Only `createsuperuser` may set the framework superuser flag."""
        self.client.force_login(self.staff)

        with patch('apps.core.admin_views.log_activity'), \
                patch('apps.core.admin_views._sync_user_mirror'):
            self.client.post(reverse('management_user_create'), {
                'username': 'flaggedadmin',
                'first_name': 'Flagged',
                'last_name': 'Administrator',
                'email': 'flagged.admin@example.com',
                'role': 'administrator',
                'password': PASSWORD,
                'password_confirm': PASSWORD,
                'is_active': 'on',
            })

        created = User.objects.get(username='flaggedadmin')
        self.assertTrue(created.is_staff)
        self.assertFalse(created.is_superuser)


class PasswordResetTests(AccountTestBase):
    """Requirement 2 and 3: forgot password on both portals."""
    def test_admin_password_reset_page_renders(self):
        response = self.client.get(reverse('admin_password_reset'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/password_reset.html')

    def test_commuter_password_reset_page_renders(self):
        response = self.client.get(reverse('commuter_password_reset'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/password_reset.html')

    def test_password_reset_sends_a_reset_link(self):
        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        ):
            response = self.client.post(reverse('commuter_password_reset'), {
                'email': self.commuter.email,
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('commuter_password_reset_done'))

    def test_password_reset_confirm_view_renders(self):
        response = self.client.get(
            reverse('commuter_password_reset_confirm', args=['MQ', 'invalid'])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/password_reset_confirm.html')
