# FILE: /backend/apps/accounts/permissions.py
from rest_framework import permissions

class IsSuperAdmin(permissions.BasePermission):
    """
    Permission check for Super Admin users.
    """
    
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == request.user.Role.SUPER_ADMIN
        )


class IsAdmin(permissions.BasePermission):
    """
    Permission check for Admin users (includes Super Admins).
    """
    
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in [request.user.Role.ADMIN, request.user.Role.SUPER_ADMIN]
        )


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allows read-only access to everyone, write access only to admins.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for admins
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in [request.user.Role.ADMIN, request.user.Role.SUPER_ADMIN]
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to only allow owners or admins to access.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin users can access anything
        if request.user.role in [request.user.Role.ADMIN, request.user.Role.SUPER_ADMIN]:
            return True
        
        # Object owner can access
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'owner'):
            return obj.owner == request.user
        elif hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class IsVerifiedUser(permissions.BasePermission):
    """
    Permission check for verified users only.
    """
    
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.is_verified
        )


class RateLimitPermission(permissions.BasePermission):
    """
    Rate limiting permission based on user/IP.
    """
    
    def has_permission(self, request, view):
        from django.core.cache import cache
        from django.conf import settings
        
        # Get client identifier
        if request.user.is_authenticated:
            identifier = f"user:{request.user.id}"
        else:
            identifier = f"ip:{request.META.get('REMOTE_ADDR')}"
        
        # Get rate limits from view or settings
        rate_limit = getattr(view, 'rate_limit', 60)  # Default 60 per hour
        time_period = getattr(view, 'time_period', 3600)  # Default 1 hour
        
        cache_key = f"ratelimit:{identifier}:{view.__class__.__name__}"
        current = cache.get(cache_key, 0)
        
        if current >= rate_limit:
            return False
        
        # Increment counter
        cache.set(cache_key, current + 1, time_period)
        return True