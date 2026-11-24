from django.db import transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class InvalidRefreshToken(Exception):
    """Raised when a refresh token cannot be used for logout."""


class RefreshTokenUserMismatch(Exception):
    """Raised when a refresh token belongs to a different user."""


@transaction.atomic
def register_user(validated_data):
    return User.objects.create_user(**validated_data)


def blacklist_refresh_token_for_user(refresh_value, user):
    try:
        token = RefreshToken(refresh_value)
    except TokenError as error:
        raise InvalidRefreshToken(
            "The refresh token is invalid or expired."
        ) from error

    if str(token.get("user_id")) != str(user.pk):
        raise RefreshTokenUserMismatch(
            "The refresh token does not belong to the authenticated user."
        )

    token.blacklist()
