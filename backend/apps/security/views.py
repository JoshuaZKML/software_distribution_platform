# FILE: backend/apps/security/views.py
from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView          # <-- added for new views
from rest_framework.response import Response      # <-- added
from django.conf import settings                  # <-- added

from .models import IPBlacklist, AbuseAttempt, AbuseAlert, SecurityNotificationLog
from .serializers import (
    IPBlacklistSerializer, AbuseAttemptSerializer,
    AbuseAlertSerializer, SecurityNotificationLogSerializer,
    SecurityLogSerializer,                         # <-- new (will be added in serializers.py)
)

# Imports for new views
from apps.accounts.models import SecurityLog        # <-- from accounts app
from apps.accounts.utils.device_fingerprint import DeviceFingerprintGenerator  # <-- if exists


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


# ============================================================================
# NEW VIEWS – added without modifying existing code
# ============================================================================

class SecuritySettingsView(APIView):
    """
    Get current security settings (admin only).
    Returns a subset of Django settings relevant to security.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        data = {
            'rate_limit_enabled': getattr(settings, 'RATE_LIMIT_ENABLED', True),
            'max_login_attempts': getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5),
            'session_timeout_minutes': getattr(settings, 'SESSION_COOKIE_AGE', 1209600) // 60,
            'mfa_required': getattr(settings, 'MFA_REQUIRED', False),
        }
        return Response(data)


class DeviceFingerprintCheckView(APIView):
    """
    Generate and return a device fingerprint based on the request.
    Useful for testing and debugging. Accessible only to authenticated users.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            fp = DeviceFingerprintGenerator.generate(request)
        except Exception as e:
            return Response(
                {'error': 'Could not generate fingerprint', 'details': str(e)},
                status=400
            )
        return Response({'device_fingerprint': fp})


class SuspiciousActivityReportView(APIView):
    """
    Return recent suspicious activities (abuse attempts + security logs).
    Admin only. Accepts optional 'limit' query parameter (default 50).
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        limit = request.GET.get('limit', 50)
        try:
            limit = int(limit)
            if limit < 1:
                limit = 50
        except ValueError:
            limit = 50

        # Fetch recent abuse attempts
        attempts = AbuseAttempt.objects.all().order_by('-created_at')[:limit]

        # Fetch security logs that are flagged as suspicious (adjust filter as needed)
        logs = SecurityLog.objects.filter(action__icontains='suspicious').order_by('-created_at')[:limit]

        data = {
            'abuse_attempts': AbuseAttemptSerializer(attempts, many=True).data,
            'security_logs': SecurityLogSerializer(logs, many=True).data,
        }
        return Response(data)


class AuditLogView(APIView):
    """
    Retrieve audit logs (admin actions). Admin only.
    Returns logs with an actor (non‑system actions), newest first, up to 100 entries.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        logs = SecurityLog.objects.filter(actor__isnull=False).order_by('-created_at')[:100]
        # Using serializer for consistent output
        serializer = SecurityLogSerializer(logs, many=True)
        return Response(serializer.data)