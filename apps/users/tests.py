import os

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.test import Client, TransactionTestCase

from apps.users import compat

ADMIN_PASSWORD = os.environ.get("SAKAY_ADMIN_PASSWORD")
COMMUTER_PASSWORD = os.environ.get("SAKAY_COMMUTER_PASSWORD")

USERS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INT NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id INT DEFAULT NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY username (username),
    UNIQUE KEY email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def create_users_table():
    with connection.cursor() as cursor:
        cursor.execute(USERS_TABLE_DDL)


def drop_users_table():
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS users")


def insert_user(user_id, username, email, password, role_id, is_active=1):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (id, username, email, password_hash, role_id, is_active) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            [user_id, username, email, make_password(password), role_id, is_active],
        )


class LegacyAuthBackendTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_users_table()

    @classmethod
    def tearDownClass(cls):
        drop_users_table()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users")

    def test_demo_users_can_log_in(self):
        if not (ADMIN_PASSWORD and COMMUTER_PASSWORD):
            self.skipTest("demo passwords not provided via environment")
        insert_user(1, "admin_demo", "admin.demo@sakayguide.test", ADMIN_PASSWORD, 2)
        insert_user(2, "commuter_demo", "commuter.demo@sakayguide.test", COMMUTER_PASSWORD, 1)

        admin = authenticate(username="admin_demo", password=ADMIN_PASSWORD)
        commuter = authenticate(username="commuter_demo", password=COMMUTER_PASSWORD)

        self.assertIsNotNone(admin)
        self.assertIsNotNone(commuter)
        self.assertTrue(admin.is_superuser)
        self.assertFalse(commuter.is_superuser)

    def test_incorrect_password_is_rejected(self):
        insert_user(10, "alice", "alice@example.com", "CorrectPass123!", 1)
        self.assertIsNone(authenticate(username="alice", password="WrongPass123!"))

    def test_unknown_user_is_rejected(self):
        self.assertIsNone(authenticate(username="nobody", password="whatever"))

    def test_inactive_user_is_rejected(self):
        insert_user(11, "inactive", "inactive@example.com", "CorrectPass123!", 1, is_active=0)
        self.assertIsNone(authenticate(username="inactive", password="CorrectPass123!"))

    def test_missing_auth_user_is_provisioned(self):
        insert_user(20, "bob", "bob@example.com", "CorrectPass123!", 2)
        user = authenticate(username="bob", password="CorrectPass123!")
        self.assertIsNotNone(user)
        self.assertEqual(user.id, 20)
        self.assertEqual(user.username, "bob")
        self.assertEqual(user.email, "bob@example.com")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertFalse(user.has_usable_password())

    def test_repeated_logins_do_not_create_duplicates(self):
        insert_user(21, "carol", "carol@example.com", "CorrectPass123!", 1)
        first = authenticate(username="carol", password="CorrectPass123!")
        second = authenticate(username="carol", password="CorrectPass123!")
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(get_user_model().objects.filter(username="carol").count(), 1)

    def test_existing_auth_user_is_reused(self):
        User = get_user_model()
        User.objects.create(
            id=30,
            username="dave",
            email="dave@example.com",
            password=make_password(None),
        )
        insert_user(30, "dave", "dave@example.com", "CorrectPass123!", 1)

        user = authenticate(username="dave", password="CorrectPass123!")
        self.assertIsNotNone(user)
        self.assertEqual(user.id, 30)
        self.assertEqual(User.objects.filter(username="dave").count(), 1)

    def test_existing_usable_auth_user_is_a_conflict(self):
        User = get_user_model()
        User.objects.create(
            id=31,
            username="erin",
            email="erin@example.com",
            password=make_password("SomeOtherPass123!"),
        )
        insert_user(31, "erin", "erin@example.com", "CorrectPass123!", 1)

        self.assertIsNone(authenticate(username="erin", password="CorrectPass123!"))
        self.assertTrue(User.objects.get(username="erin").check_password("SomeOtherPass123!"))

    def test_session_and_role_based_access(self):
        insert_user(40, "admin", "admin@example.com", "AdminPass123!", 2)
        insert_user(41, "commuter", "commuter@example.com", "CommuterPass123!", 1)

        admin_client = Client()
        self.assertTrue(admin_client.login(username="admin", password="AdminPass123!"))
        response = admin_client.get("/home/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertTrue(response.context["user"].is_superuser)

        commuter_client = Client()
        self.assertTrue(commuter_client.login(username="commuter", password="CommuterPass123!"))
        response = commuter_client.get("/home/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertFalse(response.context["user"].is_superuser)

        commuter_client.logout()
        response = commuter_client.get("/home/")
        self.assertEqual(response.status_code, 302)
