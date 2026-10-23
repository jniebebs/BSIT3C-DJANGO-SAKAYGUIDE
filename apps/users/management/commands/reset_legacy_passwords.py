"""Reset the two legacy demo users' passwords to Django-standard hashes.

Usage:
    python manage.py reset_legacy_passwords            # generate random passwords
    python manage.py reset_legacy_passwords --manual   # type each password via getpass
"""
import getpass
import secrets
import string

from django.contrib.auth.hashers import check_password, make_password
from django.core.management.base import BaseCommand
from django.db import connection, transaction

TARGETS = [
    {"id": 1, "username": "admin_demo"},
    {"id": 2, "username": "commuter_demo"},
]

SPECIALS = "!@#$%^&*"


def generate_password(length=20):
    alphabet = string.ascii_letters + string.digits + SPECIALS
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in SPECIALS for c in password)
        ):
            return password


class Command(BaseCommand):
    help = "Reset the two legacy demo users' passwords to Django-standard hashes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--manual",
            action="store_true",
            help="Type each new password interactively instead of generating one.",
        )

    def handle(self, *args, **options):
        results = []
        with transaction.atomic():
            with connection.cursor() as cursor:
                for target in TARGETS:
                    cursor.execute(
                        "SELECT id, username, updated_at FROM users WHERE id = %s",
                        [target["id"]],
                    )
                    row = cursor.fetchone()
                    if row is None:
                        raise SystemExit(f"Target user id={target['id']} not found.")
                    user_id, username, updated_at = row

                    if options["manual"]:
                        password = getpass.getpass(f"New password for {username}: ")
                        confirm = getpass.getpass(f"Confirm password for {username}: ")
                        if password != confirm:
                            raise SystemExit("Passwords do not match.")
                        if not password:
                            raise SystemExit("Password cannot be empty.")
                    else:
                        password = generate_password()

                    new_hash = make_password(password)

                    cursor.execute(
                        "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
                        [new_hash, updated_at, user_id],
                    )

                    cursor.execute(
                        "SELECT password_hash FROM users WHERE id = %s",
                        [user_id],
                    )
                    stored = cursor.fetchone()[0]
                    if not check_password(password, stored):
                        raise SystemExit(f"Verification failed for {username}.")

                    results.append((username, password))

        self.stdout.write(self.style.SUCCESS("Password reset committed for:"))
        for username, password in results:
            self.stdout.write(f"  {username}: {password}")
        self.stdout.write("Store these now; they are shown only once.")
