"""Audit helpers for SakayGuide account and administrative actions.

The ``admin_activity_logs`` table lives in the ``sakayguide`` database and
references ``users.user_id``.  Django authentication uses a separate
``auth_user`` table, so this module first mirrors the Django account into
SakayGuide's ``users`` table and then writes the audit row there.
"""
import logging

from django.db import DatabaseError, IntegrityError, transaction
from django.utils.crypto import get_random_string

from routes.models import AdminActivityLog, SakayUser

logger = logging.getLogger(__name__)

SAKAYGUIDE_ALIAS = 'sakayguide'
ROLE_ADMIN = 'admin'
ROLE_COMMUTER = 'commuter'


def sakay_user_for(django_user, role=None):
    """Return the SakayGuide ``users`` row for a Django user.

    Existing rows are matched by e-mail. When no row exists a mirror account
    is created with an opaque password (Django remains the authentication
    source of truth).
    """
    if django_user is None or not getattr(django_user, 'is_authenticated', False):
        return None

    email = (django_user.email or '').strip().lower()
    if email:
        existing = SakayUser.objects.filter(email__iexact=email).first()
        if existing is not None:
            return existing

    mirror_email = email or f'user{django_user.pk}@sakayguide.local'
    full_name = django_user.get_full_name().strip() or django_user.username
    if role is None:
        role = ROLE_ADMIN if django_user.is_staff else ROLE_COMMUTER

    try:
        with transaction.atomic(using=SAKAYGUIDE_ALIAS):
            return SakayUser.objects.create(
                full_name=full_name,
                email=mirror_email,
                # Opaque value; real login uses Django's password hashers.
                password=f'unused-{get_random_string(32)}',
                role=role,
                status='active',
            )
    except IntegrityError:
        return SakayUser.objects.filter(email__iexact=mirror_email).first()


def log_activity(actor, action_type, table_affected, record_id=None,
                 description=''):
    """Append an audit row, returning it or ``None`` when logging fails.

    Logging must never break the action being audited (for example account
    registration when the SakayGuide database is temporarily unavailable).
    """
    try:
        actor_row = sakay_user_for(actor)
        if actor_row is None:
            return None
        return AdminActivityLog.objects.create(
            admin_id=actor_row.user_id,
            action_type=action_type[:50],
            table_affected=table_affected[:64],
            record_id=record_id,
            action_description=description,
        )
    except (DatabaseError, RuntimeError) as exc:
        logger.warning('Could not write SakayGuide audit log: %s', exc)
        return None


def log_account_creation(actor, account, account_role, description):
    """Mirror a newly created account and log its creation."""
    try:
        account_row = sakay_user_for(account, role=account_role)
        if account_row is None:
            return None
        return log_activity(
            actor,
            'CREATE',
            'users',
            account_row.user_id,
            description,
        )
    except (DatabaseError, RuntimeError) as exc:
        logger.warning('Could not record SakayGuide account creation: %s', exc)
        return None
