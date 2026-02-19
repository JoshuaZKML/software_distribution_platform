from rest_framework import permissions
from django.db.models import Q
from django.utils import timezone
from .models import TicketBan


class IsTicketOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.role in ['ADMIN', 'SUPER_ADMIN']:
            return True
        return obj.user == user


class NotBannedFromTickets(permissions.BasePermission):
    def has_permission(self, request, view):
        if view.action == 'create':
            return not TicketBan.objects.filter(
                user=request.user
            ).filter(
                Q(is_permanent=True) | Q(expires_at__gt=timezone.now())
            ).exists()
        return True