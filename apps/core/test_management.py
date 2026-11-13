"""Security and access-control tests for the administrator dashboard."""
import re
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.core.management.commands.create_admin import Command as CreateAdminCommand

User = get_user_model()
PASSWORD = 'Str0ng!Passw0rd2026'


class ManagementAccessTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='rootadmin',
            email='root@example.com',
            password=PASSWORD,
        )
        self.staff = User.objects.create_user(
            username='staffadmin',
            email='staff@example.com',
            password=PASSWORD,
            is_staff=True,
        )
        self.commuter = User.objects.create_user(
            username='commuter',
            email='commuter@example.com',
            password=PASSWORD,
        )

    @patch('apps.core.admin_views._dashboard_stats', return_value={
        'total_users': 3,
        'total_commuters': 1,
        'total_admins': 2,
        'superusers': 1,
    })
    def test_staff_can_open_management_dashboard(self, stats_mock):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('management_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'management/dashboard.html')
        self.assertContains(response, 'Dashboard overview')
        self.assertContains(response, 'Total users')
        self.assertContains(response, reverse('management_locations'))
        stats_mock.assert_called_once()

    def test_commuter_is_redirected_away_from_management(self):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('management_dashboard'))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Access denied', status_code=403)

    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(reverse('management_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('admin_login')))

    @patch('apps.core.views._sakayguide_stats', return_value={})
    def test_staff_dashboard_links_to_management_console(self, stats_mock):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Management dashboard')
        self.assertContains(response, reverse('management_dashboard'))
        self.assertContains(response, 'Administrator')

    @patch('apps.core.views._sakayguide_stats', return_value={})
    def test_commuter_is_redirected_away_from_monitoring(self, stats_mock):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 403)


class LoginAndSessionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='stafflogin',
            email='Staff.Login@Example.com',
            password=PASSWORD,
            is_staff=True,
        )
        self.commuter = User.objects.create_user(
            username='commuterlogin',
            email='Commuter.Login@Example.com',
            password=PASSWORD,
        )

    @patch('apps.core.views.log_activity')
    def test_username_login_redirects_administrator_to_console(self, log_mock):
        response = self.client.post(reverse('login'), {
            'username': 'stafflogin',
            'password': PASSWORD,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('management_dashboard'))
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.staff.pk
        )

    @patch('apps.core.views.log_activity')
    def test_email_login_is_case_insensitive_and_redirects_admin(self, log_mock):
        response = self.client.post(reverse('login'), {
            'username': 'STAFF.LOGIN@EXAMPLE.COM',
            'password': PASSWORD,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('management_dashboard'))
        self.assertEqual(
            int(self.client.session['_auth_user_id']), self.staff.pk
        )

    @patch('apps.core.views.log_activity')
    def test_commuter_login_redirects_to_commuter_dashboard(self, log_mock):
        response = self.client.post(reverse('login'), {
            'username': 'commuterlogin',
            'password': PASSWORD,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('commuter_dashboard'))

    @patch('apps.core.views.log_activity')
    def test_invalid_login_does_not_authenticate(self, log_mock):
        response = self.client.post(reverse('login'), {
            'username': 'commuterlogin',
            'password': 'wrong-password',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_rejects_get_requests(self):
        self.client.force_login(self.commuter)

        response = self.client.get(reverse('logout'))

        self.assertEqual(response.status_code, 405)

    @patch('apps.core.views.log_activity')
    def test_logout_post_clears_session(self, log_mock):
        self.client.force_login(self.commuter)

        response = self.client.post(reverse('logout'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)
        log_mock.assert_called_once()

    def test_management_post_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)

        response = csrf_client.post(reverse('management_user_create'), {})

        self.assertEqual(response.status_code, 403)


class UserManagementRulesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='superadmin',
            email='super@example.com',
            password=PASSWORD,
        )
        self.staff = User.objects.create_user(
            username='plainadmin',
            email='plain@example.com',
            password=PASSWORD,
            is_staff=True,
        )
        self.commuter = User.objects.create_user(
            username='regularcommuter',
            email='regular@example.com',
            password=PASSWORD,
        )

    def test_administrator_can_promote_commuter(self):
        """Every administrator may assign the administrator role."""
        self.client.force_login(self.staff)

        with patch('apps.core.admin_views.log_activity'), \
                patch('apps.core.admin_views._sync_user_mirror'):
            response = self.client.post(
                reverse('management_user_edit', args=[self.commuter.pk]),
                {
                    'username': self.commuter.username,
                    'first_name': '',
                    'last_name': '',
                    'email': self.commuter.email,
                    'role': 'administrator',
                    'is_active': 'on',
                },
            )

        self.assertEqual(response.status_code, 302)
        self.commuter.refresh_from_db()
        self.assertTrue(self.commuter.is_staff)

    def test_administrator_can_edit_another_administrator(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse('management_user_edit', args=[self.admin.pk])
        )

        self.assertEqual(response.status_code, 200)

    def test_role_choices_offer_only_commuter_and_administrator(self):
        from apps.core.admin_forms import ROLE_CHOICES, role_for

        self.assertEqual(
            ROLE_CHOICES,
            [('commuter', 'Commuter'), ('administrator', 'Administrator')],
        )
        # A Django superuser is an administrator, not a third role.
        self.assertEqual(role_for(self.admin), 'administrator')
        self.assertEqual(role_for(self.staff), 'administrator')
        self.assertEqual(role_for(self.commuter), 'commuter')

    @patch('apps.core.admin_views.log_activity')
    @patch('apps.core.admin_views._sync_user_mirror')
    def test_administrator_can_promote_commuter_with_audit(self, mirror_mock, log_mock):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('management_user_edit', args=[self.commuter.pk]),
            {
                'username': self.commuter.username,
                'first_name': 'Now',
                'last_name': 'Administrator',
                'email': self.commuter.email,
                'role': 'administrator',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('management_users'))
        self.commuter.refresh_from_db()
        self.assertTrue(self.commuter.is_staff)
        # The Django superuser flag is never granted through the app UI.
        self.assertFalse(self.commuter.is_superuser)
        mirror_mock.assert_called_once()
        log_mock.assert_called_once()

    def test_administrator_cannot_deactivate_own_account(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('management_user_edit', args=[self.staff.pk]),
            {
                'username': self.staff.username,
                'first_name': '',
                'last_name': '',
                'email': self.staff.email,
                'role': 'administrator',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You cannot deactivate your own account.')
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    def test_administrator_cannot_demote_self(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('management_user_edit', args=[self.admin.pk]),
            {
                'username': self.admin.username,
                'first_name': '',
                'last_name': '',
                'email': self.admin.email,
                'role': 'commuter',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'You cannot remove your own administrator access.'
        )
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(self.admin.is_superuser)

    def test_last_active_administrator_is_never_left_without_one(self):
        """The console must always keep one usable administrator.

        The self-protection rule fires first when an administrator edits
        their own account, and the last-administrator guard covers the
        remaining case.
        """
        from apps.core.admin_views import _last_active_administrator

        self.staff.is_active = False
        self.staff.save(update_fields=['is_active'])

        self.assertTrue(_last_active_administrator(self.admin))
        self.assertFalse(_last_active_administrator(self.commuter))

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('management_user_edit', args=[self.admin.pk]),
            {
                'username': self.admin.username,
                'first_name': '',
                'last_name': '',
                'email': self.admin.email,
                'role': 'commuter',
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'You cannot remove your own administrator access.'
        )
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_staff)

    def test_administrator_cannot_deactivate_self_by_toggle(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('management_user_toggle', args=[self.staff.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)

    @patch('apps.core.admin_views.log_activity')
    @patch('apps.core.admin_views._sync_user_mirror')
    def test_administrator_can_create_commuter(self, mirror_mock, log_mock):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('management_user_create'),
            {
                'username': 'newcommuter',
                'first_name': 'New',
                'last_name': 'Commuter',
                'email': 'newcommuter@example.com',
                'role': 'commuter',
                'password': PASSWORD,
                'password_confirm': PASSWORD,
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username='newcommuter')
        self.assertFalse(created.is_staff)
        self.assertTrue(created.is_active)
        mirror_mock.assert_called_once()
        log_mock.assert_called_once()

    @patch('apps.core.admin_views.log_activity')
    @patch('apps.core.admin_views._sync_user_mirror')
    def test_administrator_can_create_another_administrator(self, mirror_mock, log_mock):
        """Any administrator may create other administrator accounts."""
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('management_user_create'),
            {
                'username': 'newadministrator',
                'first_name': 'New',
                'last_name': 'Administrator',
                'email': 'newadministrator@example.com',
                'role': 'administrator',
                'password': PASSWORD,
                'password_confirm': PASSWORD,
                'is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username='newadministrator')
        self.assertTrue(created.is_staff)
        self.assertTrue(created.is_active)
        # The Django superuser flag is only granted by createsuperuser.
        self.assertFalse(created.is_superuser)


class CreateAdminCommandTests(TestCase):
    @patch.object(CreateAdminCommand, '_mirror_account')
    def test_command_creates_administrator_and_writes_gitignored_env(
        self, mirror_mock
    ):
        out = StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command(
                    'create_admin',
                    username='bootstrapadmin',
                    email='bootstrap@example.com',
                    noinput=True,
                    stdout=out,
                )

            env_text = Path(temp_dir, '.env').read_text(encoding='utf-8')
            env = {
                key: value
                for key, value in (
                    line.split('=', 1)
                    for line in env_text.splitlines()
                    if '=' in line and not line.lstrip().startswith('#')
                )
            }

        user = User.objects.get(username='bootstrapadmin')
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password(env['INITIAL_ADMIN_PASSWORD']))
        self.assertNotIn(env['INITIAL_ADMIN_PASSWORD'], out.getvalue())
        self.assertEqual(env['INITIAL_ADMIN_USERNAME'], 'bootstrapadmin')
        self.assertEqual(env['INITIAL_ADMIN_EMAIL'], 'bootstrap@example.com')
        mirror_mock.assert_called_once()

    @patch.object(CreateAdminCommand, '_mirror_account')
    def test_command_refuses_duplicate_username(self, mirror_mock):
        User.objects.create_user(
            username='existingadmin',
            email='existing@example.com',
            password=PASSWORD,
        )

        with self.assertRaisesMessage(CommandError, 'already exists'):
            call_command(
                'create_admin',
                username='ExistingAdmin',
                email='different@example.com',
                noinput=True,
                no_env=True,
            )
        mirror_mock.assert_not_called()

    @patch.object(CreateAdminCommand, '_mirror_account')
    def test_no_env_option_prints_password_once(self, mirror_mock):
        out = StringIO()

        call_command(
            'create_admin',
            username='printedadmin',
            email='printed@example.com',
            noinput=True,
            no_env=True,
            stdout=out,
        )

        output = out.getvalue()
        match = re.search(
            r'Initial password \(shown once\): (\S+)', output
        )
        self.assertIsNotNone(match)
        user = User.objects.get(username='printedadmin')
        self.assertTrue(user.check_password(match.group(1)))
        self.assertIn('Change this password immediately', output)

    @patch.object(CreateAdminCommand, '_mirror_account')
    def test_command_creates_one_administrator_role(self, mirror_mock):
        """There is a single administrator role, with no second tier.

        The Django superuser flag is a framework permission (it opens the
        built-in Django admin site); the application role is still just
        "administrator".
        """
        from apps.core.admin_forms import role_for

        call_command(
            'create_admin',
            username='plainbootstrap',
            email='plainbootstrap@example.com',
            noinput=True,
            no_env=True,
            stdout=StringIO(),
        )

        user = User.objects.get(username='plainbootstrap')
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertEqual(role_for(user), 'administrator')
