# FILE: backend/apps/security/views.py
from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination

from .models import IPBlacklist, AbuseAttempt, AbuseAlert, SecurityNotificationLog
from .serializers import (
    IPBlacklistSerializer, AbuseAttemptSerializer,
    AbuseAlertSerializer, SecurityNotificationLogSerializer
)


# ============================================================================
# Custom Permissions
# ============================================================================
class IsSuperUser(permissions.BasePermission):
    """
    Allows access only to superusers.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


# ============================================================================
# Standard Pagination for Security Endpoints
# ============================================================================
class SecurityPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


# ============================================================================
# IP Blacklist (CRUD with strict permissions)
# ============================================================================
class IPBlacklistViewSet(viewsets.ModelViewSet):
    """
    CRUD for IP blacklist entries.
    - Superusers can create, update, delete.
    - Staff members can only view.
    - Supports filtering by IP network, active status, and searching by network.
    """
    queryset = IPBlacklist.objects.all().order_by('-created_at')
    serializer_class = IPBlacklistSerializer
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['ip_network', 'active']
    search_fields = ['ip_network', 'reason']
    ordering_fields = ['created_at', 'ip_network']
    ordering = ['-created_at']

    def get_permissions(self):
        """
        - Write actions (create, update, partial_update, destroy): require superuser.
        - Read actions (list, retrieve): require staff (IsAdminUser).
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsSuperUser]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [p() for p in permission_classes]


# ============================================================================
# Abuse Attempts (Read‑only, admin only)
# ============================================================================
class AbuseAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read‑only view of abuse attempts.
    - Access restricted to staff.
    - Supports filtering by IP, path, and date range.
    """
    queryset = AbuseAttempt.objects.all().order_by('-created_at')
    serializer_class = AbuseAttemptSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['ip_address', 'path', 'method']
    search_fields = ['ip_address', 'path', 'user_agent']
    ordering_fields = ['created_at', 'ip_address']
    ordering = ['-created_at']


# ============================================================================
# Abuse Alerts (Read‑only, admin only)
# ============================================================================
class AbuseAlertViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read‑only view of abuse alerts.
    - Access restricted to staff.
    - Supports filtering by severity, status, and date.
    """
    queryset = AbuseAlert.objects.all().order_by('-created_at')
    serializer_class = AbuseAlertSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['severity', 'resolved']
    search_fields = ['message', 'ip_address']
    ordering_fields = ['created_at', 'severity']
    ordering = ['-created_at']


# ============================================================================
# Security Notification Logs (Read‑only, admin only)
# ============================================================================
class SecurityNotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read‑only view of security notification logs.
    - Access restricted to staff.
    - Supports filtering by recipient, type, and date.
    """
    queryset = SecurityNotificationLog.objects.all().order_by('-created_at')
    serializer_class = SecurityNotificationLogSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = SecurityPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'recipient']
    search_fields = ['recipient', 'subject']
    ordering_fields = ['created_at', 'notification_type']
    ordering = ['-created_at']