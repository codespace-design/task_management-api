from rest_framework.permissions import BasePermission

from .models import User


class RolePermission(BasePermission):
    role = None

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == self.role
        )


class IsAdminRole(RolePermission):
    role = User.Role.ADMIN


class IsEmployer(RolePermission):
    role = User.Role.EMPLOYER


class IsCandidate(RolePermission):
    role = User.Role.CANDIDATE
