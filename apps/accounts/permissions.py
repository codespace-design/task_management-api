from rest_framework.permissions import BasePermission

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
