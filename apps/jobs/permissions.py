from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import User


class IsEmployerOwnerOrReadOnly(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if view.action in {
            "create",
            "update",
            "partial_update",
            "activate",
            "deactivate",
        }:
            return request.user.role == User.Role.EMPLOYER
        return True

    def has_object_permission(self, request, view, obj):
        if view.action in {"update", "partial_update", "activate", "deactivate"}:
            return bool(
                request.user.role == User.Role.EMPLOYER
                and obj.employer_id == request.user.pk
            )
        return True
