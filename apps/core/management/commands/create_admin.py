"""Create a one-time SakayGuide administrator account safely.

SakayGuide has a single administrator role, so this command creates one
account with the administrator role and the Django superuser flag (which is
what grants access to the built-in Django admin site).

The command generates the password instead of accepting it on the command
line, refuses duplicate usernames/e-mail addresses, and writes the initial
credentials to the gitignored ``.env`` file by default. The password is never
hard-coded in source control and is only shown on screen when explicitly
requested.

Typical use::

    python manage.py create_admin --username sakayadmin \
        --email admin@example.com --first-name Sakay --last-name Admin

After signing in, change the password and remove the ``INITIAL_ADMIN_*`` lines
from ``.env``.
"""
import secrets
import string
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import DatabaseError

from apps.core.audit import log_activity, sakay_user_for

ENV_KEYS = (
    'INITIAL_ADMIN_USERNAME',
    'INITIAL_ADMIN_EMAIL',
    'INITIAL_ADMIN_PASSWORD',
)
PASSWORD_ALPHABET = string.ascii_letters + string.digits + '!@#$%^&*()-_=+[]{}'


def _generate_password():
    """Return a strong password that satisfies Django's validators."""
    while True:
        password = ''.join(
            secrets.choice(PASSWORD_ALPHABET) for _ in range(24)
        )
        has_upper = any(char.isupper() for char in password)
        has_lower = any(char.islower() for char in password)
        has_digit = any(char.isdigit() for char in password)
        has_symbol = any(char in PASSWORD_ALPHABET[62:] for char in password)
        if not (has_upper and has_lower and has_digit and has_symbol):
            continue
        try:
            validate_password(password)
        except ValidationError:
            continue
        return password


def _update_env_file(path, values):
    """Add or replace the initial admin keys in ``.env``.

    Only the named keys are touched; unrelated settings (for example the
    Google Maps key) are preserved. The file is created with restrictive
    content when it does not exist yet.
    """
    path = Path(path)
    existing = ''
    if path.exists():
        existing = path.read_text(encoding='utf-8')

    replaced = {key: False for key in values}
    lines = existing.splitlines()
    output = []
    for line in lines:
        stripped = line.strip()
        key = stripped.split('=', 1)[0].strip() if '=' in stripped else ''
        if key in values and not stripped.startswith('#'):
            output.append(f'{key}={values[key]}')
            replaced[key] = True
        else:
            output.append(line)

    missing = [key for key, done in replaced.items() if not done]
    if output and output[-1].strip():
        output.append('')
    if missing:
        output.append('# Initial SakayGuide administrator (remove after first login)')
        for key in missing:
            output.append(f'{key}={values[key]}')

    path.write_text('\n'.join(output).rstrip() + '\n', encoding='utf-8')


class Command(BaseCommand):
    help = (
        'Create a secure SakayGuide administrator account and store its '
        'generated initial password in the gitignored .env file.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', help='Administrator username.')
        parser.add_argument('--email', help='Administrator e-mail address.')
        parser.add_argument('--first-name', default='', help='First name.')
        parser.add_argument('--last-name', default='', help='Last name.')
        parser.add_argument(
            '--no-env',
            action='store_true',
            help=(
                'Do not write INITIAL_ADMIN_* values to .env. The generated '
                'password is printed once instead.'
            ),
        )
        parser.add_argument(
            '--show-password',
            action='store_true',
            help=(
                'Print the generated password once as well as writing it to '
                '.env. Avoid this on shared or recorded terminals.'
            ),
        )
        parser.add_argument(
            '--noinput',
            '--no-input',
            action='store_true',
            dest='noinput',
            help='Do not prompt for missing username/e-mail values.',
        )

    def handle(self, *args, **options):
        username = (options.get('username') or '').strip()
        email = (options.get('email') or '').strip()

        if not username:
            if options['noinput']:
                raise CommandError('--username is required with --noinput.')
            username = input('Administrator username: ').strip()
        if not email:
            if options['noinput']:
                raise CommandError('--email is required with --noinput.')
            email = input('Administrator e-mail: ').strip()

        self._validate_username(username)
        self._validate_email(email)
        self._ensure_unique(username, email)

        password = _generate_password()
        User = get_user_model()

        try:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name=options['first_name'].strip(),
                last_name=options['last_name'].strip(),
            )
        except Exception as exc:  # pragma: no cover - defensive database guard
            raise CommandError(f'Could not create the administrator: {exc}') from exc

        env_path = Path(settings.BASE_DIR) / '.env'
        write_env = not options['no_env']
        if write_env:
            _update_env_file(
                env_path,
                {
                    'INITIAL_ADMIN_USERNAME': username,
                    'INITIAL_ADMIN_EMAIL': email,
                    'INITIAL_ADMIN_PASSWORD': password,
                },
            )

        self._mirror_account(user)

        self.stdout.write(self.style.SUCCESS('Administrator account created.'))
        self.stdout.write(f'  Username: {username}')
        self.stdout.write(f'  Email:    {email}')
        self.stdout.write('  Role:     administrator')
        if write_env:
            self.stdout.write(
                f'  Initial password saved to: {env_path} '
                '(gitignored; remove INITIAL_ADMIN_* after first login)'
            )
        if options['show_password'] or not write_env:
            self.stdout.write(
                f'  Initial password (shown once): {password}'
            )
            self.stdout.write(
                self.style.WARNING(
                    'Change this password immediately after signing in.'
                )
            )
        else:
            self.stdout.write(
                '  Open .env to read INITIAL_ADMIN_PASSWORD, sign in, then '
                'change the password and delete the INITIAL_ADMIN_* lines.'
            )

    @staticmethod
    def _validate_username(username):
        validator = UnicodeUsernameValidator()
        try:
            validator(username)
        except ValidationError as exc:
            raise CommandError(f'Invalid username: {"; ".join(exc.messages)}') from exc
        if len(username) > 150:
            raise CommandError('Username must be 150 characters or fewer.')

    @staticmethod
    def _validate_email(email):
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError(f'Invalid e-mail address: {email}') from exc

    @staticmethod
    def _ensure_unique(username, email):
        User = get_user_model()
        if User.objects.filter(username__iexact=username).exists():
            raise CommandError(
                f'An account with username "{username}" already exists. '
                'Use a different username or manage the existing account in '
                'the management dashboard.'
            )
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                f'An account with e-mail "{email}" already exists. '
                'Use a different e-mail address or manage the existing account.'
            )

    @staticmethod
    def _mirror_account(user):
        """Best-effort SakayGuide mirror + audit entry.

        The Django account is authoritative, so a temporarily unavailable
        transit database must not make account creation fail.
        """
        try:
            mirror = sakay_user_for(user, role='admin', status='active')
            if mirror is not None:
                log_activity(
                    user,
                    'CREATE',
                    'users',
                    mirror.user_id,
                    'Administrator account created with create_admin.',
                )
        except (DatabaseError, RuntimeError):
            pass
