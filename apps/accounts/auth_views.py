from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import (
    InvalidRefreshToken,
    RefreshTokenUserMismatch,
    blacklist_refresh_token_for_user,
)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            blacklist_refresh_token_for_user(
                serializer.validated_data["refresh"],
                request.user,
            )
        except (InvalidRefreshToken, RefreshTokenUserMismatch) as error:
            raise ValidationError({"refresh": [str(error)]}) from error
        return Response(status=status.HTTP_205_RESET_CONTENT)
