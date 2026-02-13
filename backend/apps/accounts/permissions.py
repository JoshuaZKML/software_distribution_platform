# FILE: /backend/apps/accounts/permissions.py
from rest_framework import permissions
from django.core.cache import cache
from .models import User  # import for role constants and defensive checks


# ----------------------------------------------------------------------
# Role constants – defined once to avoid repetition (non‑disruptive)
# ----------------------------------------------------------------------
ADMIN_ROLES = [User.Role.ADMIN, User.Role.SUPER_ADMIN]


def _get_client_ip(request):
    """
    Extract the real client IP address from request headers.
    Handles reverse proxies and load balancers.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first IP in the chain (original client)
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ----------------------------------------------------------------------
# Role‑based permissions
# ----------------------------------------------------------------------
class IsSuperAdmin(permissions.BasePermission):
    """
    Permission check for Super Admin users.
    """

    def has_permission(self, request, view):
        # Defensive check: ensure user is authenticated and has a role attribute
        user = request.user
        if not (user and getattr(user, 'is_authenticated', False)):
            return False
        return getattr(user, 'role', None) == User.Role.SUPER_ADMIN


class IsAdmin(permissions.BasePermission):
    """
    Permission check for Admin users (includes Super Admins).
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and getattr(user, 'is_authenticated', False)):
            return False
        return getattr(user, 'role', None) in ADMIN_ROLES


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allows read‑only access to everyone, write access only to admins.
    """

    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for admins
        user = request.user
        if not (user and getattr(user, 'is_authenticated', False)):
            return False
        return getattr(user, 'role', None) in ADMIN_ROLES


# ----------------------------------------------------------------------
# Object‑level permissions
# ----------------------------------------------------------------------
class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object‑level permission: only owners or admins may access.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        # Anonymous users are never allowed
        if not (user and getattr(user, 'is_authenticated', False)):
            return False

        # Admin users can access anything
        if getattr(user, 'role', None) in ADMIN_ROLES:
            return True

        # Object owner checks – tries common field names
        for attr in ['user', 'owner', 'created_by']:
            if hasattr(obj, attr) and getattr(obj, attr) == user:
                return True

        return False


# ----------------------------------------------------------------------
# Verified user check
# ----------------------------------------------------------------------
class IsVerifiedUser(permissions.BasePermission):
    """
    Permission check for verified users only.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and getattr(user, 'is_authenticated', False)):
            return False
        return getattr(user, 'is_verified', False)


# ----------------------------------------------------------------------
# Atomic rate‑limiting with improved IP detection
# ----------------------------------------------------------------------
class RateLimitPermission(permissions.BasePermission):
    """
    Rate limiting permission based on user ID or client IP.
    Uses atomic cache increment to prevent race conditions.
    """

    def has_permission(self, request, view):
        from django.conf import settings

        # 1. Determine client identifier
        if request.user.is_authenticated:
            identifier = f"user:{request.user.id}"
        else:
            client_ip = _get_client_ip(request)
            identifier = f"ip:{client_ip}"

        # 2. Get limits from view or settings
        rate_limit = getattr(view, 'rate_limit', 60)        # default 60 per hour
        time_period = getattr(view, 'time_period', 3600)    # default 1 hour

        # 3. Atomic counter – works with Redis/Memcached that support incr
        cache_key = f"ratelimit:{identifier}:{view.__class__.__name__}"

        try:
            current = cache.incr(cache_key)
            if current == 1:
                # First hit – set expiry
                cache.expire(cache_key, time_period)
        except ValueError:
            # Key does not exist – set initial value 1 with expiry
            cache.set(cache_key, 1, time_period)
            current = 1

        if current > rate_limit:
            return False

        return True
