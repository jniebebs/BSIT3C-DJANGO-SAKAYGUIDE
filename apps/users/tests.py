from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserSaveAuditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='siteadmin',
            email='siteadmin@example.com',
            password='secret1234',
        )
        self.client.force_login(self.admin)

    @patch('apps.users.views.log_account_creation')
    def test_admin_creating_commuter_writes_audit_log(self, log_mock):
        response = self.client.post(reverse('users:user_save_ajax'), {
            'username': 'createdcommuter',
            'first_name': 'Created',
            'last_name': 'Commuter',
            'email': 'createdcommuter@example.com',
            'password': 'Str0ng!Passw0rd',
            'is_active': 'true',
            'is_staff': 'false',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        log_mock.assert_called_once()
        kwargs = log_mock.call_args.kwargs
        self.assertEqual(kwargs['actor'], self.admin)
        self.assertEqual(kwargs['account'].username, 'createdcommuter')
        self.assertEqual(kwargs['account_role'], 'commuter')
        self.assertIn('created a commuter account', kwargs['description'])

    @patch('apps.users.views.log_account_creation')
    def test_admin_creating_administrator_writes_audit_log(self, log_mock):
        response = self.client.post(reverse('users:user_save_ajax'), {
            'username': 'createdadmin',
            'first_name': 'Created',
            'last_name': 'Administrator',
            'email': 'createdadmin@example.com',
            'password': 'Str0ng!Passw0rd',
            'is_active': 'true',
            'is_staff': 'true',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')

        log_mock.assert_called_once()
        kwargs = log_mock.call_args.kwargs
        self.assertEqual(kwargs['account'].username, 'createdadmin')
        self.assertEqual(kwargs['account_role'], 'admin')
        self.assertIn('created an administrator account', kwargs['description'])

    @patch('apps.users.views.log_account_creation')
    def test_updating_existing_user_does_not_write_creation_log(self, log_mock):
        user = User.objects.create_user(
            username='existinguser',
            email='existinguser@example.com',
            password='secret1234',
        )

        response = self.client.post(reverse('users:user_save_ajax'), {
            'id': user.pk,
            'username': user.username,
            'first_name': 'Updated',
            'last_name': 'User',
            'email': user.email,
            'is_active': 'true',
            'is_staff': 'false',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        log_mock.assert_not_called()
