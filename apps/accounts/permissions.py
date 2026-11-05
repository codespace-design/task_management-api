from rest_framework.permissions import BasePermission, IsAuthenticated

from .models import User


class RolePermission(BasePermission):
    roles = ()

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.roles
        )


class IsAdmin(RolePermission):
    roles = (User.Role.ADMIN,)


class IsAdminRole(IsAdmin):
    """Backward-compatible name for the admin role permission."""


class IsEmployer(RolePermission):
    roles = (User.Role.EMPLOYER,)


class IsCandidate(RolePermission):
    roles = (User.Role.CANDIDATE,)


class IsEmployerOrAdmin(RolePermission):
    roles = (User.Role.EMPLOYER, User.Role.ADMIN)


class IsProfileOwnerOrAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return bool(
            super().has_permission(request, view)
            and request.user.role in (view.profile_role, User.Role.ADMIN)
        )

    def has_object_permission(self, request, view, obj):
        profile_user_id = getattr(obj, "user_id", obj.pk)
        return bool(
            request.user.role == User.Role.ADMIN or profile_user_id == request.user.pk
        )
