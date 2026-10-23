import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction

from .models import LegacyUser

logger = logging.getLogger(__name__)

ADMIN_ROLE_ID = 2


class LegacyAuthBackend(BaseBackend):
    """Authenticate against the legacy ``users`` table.

    Passwords are verified with Django's standard ``check_password``. On a
    successful login a Django ``auth_user`` mirror is provisioned lazily so
    that Django's session framework can persist the login.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(LegacyUser.USERNAME_FIELD)
        if username is None or password is None:
            return None

        try:
            legacy_user = LegacyUser.objects.get(username=username)
        except LegacyUser.DoesNotExist:
            return None

        if not legacy_user.is_active:
            return None
        if not check_password(password, legacy_user.password_hash):
            return None

        return self._provision(legacy_user)

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def _provision(self, legacy_user):
        User = get_user_model()
        try:
            with transaction.atomic():
                mirror = User.objects.filter(pk=legacy_user.id).first()
                if mirror is None:
                    mirror = User.objects.filter(username=legacy_user.username).first()

                if mirror is None:
                    mirror = User(
                        id=legacy_user.id,
                        username=legacy_user.username,
                        email=legacy_user.email,
                        is_staff=legacy_user.role_id == ADMIN_ROLE_ID,
                        is_superuser=legacy_user.role_id == ADMIN_ROLE_ID,
                        is_active=legacy_user.is_active,
                    )
                    mirror.password = make_password(None)
                    mirror.save()
                elif (
                    not mirror.has_usable_password()
                    and mirror.username == legacy_user.username
                ):
                    mirror.email = legacy_user.email
                    mirror.is_staff = legacy_user.role_id == ADMIN_ROLE_ID
                    mirror.is_superuser = legacy_user.role_id == ADMIN_ROLE_ID
                    mirror.is_active = legacy_user.is_active
                    mirror.save()
                else:
                    logger.warning(
                        "auth_user conflict for legacy user id=%s", legacy_user.id
                    )
                    return None

                return mirror
        except IntegrityError:
            mirror = User.objects.filter(pk=legacy_user.id).first()
            if mirror is not None and not mirror.has_usable_password():
                return mirror
            logger.warning(
                "auth_user provisioning conflict for legacy user id=%s", legacy_user.id
            )
            return None
