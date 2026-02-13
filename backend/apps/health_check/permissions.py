from rest_framework.permissions import BasePermission

class IsSuperAdmin(BasePermission):
    """
    Permission check for Super Admin users.
    Uses your User model's `is_super_admin` property.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_super_admin
        )