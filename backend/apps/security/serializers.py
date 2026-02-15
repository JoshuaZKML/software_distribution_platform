"""
Serializers for security models.
Ensures proper validation, read‑only fields, and security.
"""
import ipaddress
from rest_framework import serializers
from .models import (
    IPBlacklist,
    AbuseAttempt,
    AbuseAlert,
    SecurityNotificationLog,
    CodeBlacklist
)

# Import SecurityLog from accounts app (needed for new views)
from apps.accounts.models import SecurityLog


class IPBlacklistSerializer(serializers.ModelSerializer):
    """
    Serializer for IP blacklist entries.
    """
    class Meta:
        model = IPBlacklist
        fields = [
            'id', 'ip_network', 'reason', 'expires_at',
            'active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_ip_network(self, value):
        """
        Validate that the value is a valid CIDR notation or IP address.
        Uses Python's ipaddress module for robust validation.
        """
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError as e:
            raise serializers.ValidationError(f"Invalid IP or CIDR format: {e}")
        return value


class AbuseAttemptSerializer(serializers.ModelSerializer):
    """
    Serializer for abuse attempts (read‑only for admins).
    Exposes only necessary fields; sensitive request data is excluded.
    """
    class Meta:
        model = AbuseAttempt
        fields = [
            'id', 'ip_address', 'path', 'method',
            'status_code', 'user_agent', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AbuseAlertSerializer(serializers.ModelSerializer):
    """
    Serializer for abuse alerts (read‑only for admins).
    """
    class Meta:
        model = AbuseAlert
        fields = [
            'id', 'ip_address', 'severity', 'message',
            'resolved', 'resolved_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SecurityNotificationLogSerializer(serializers.ModelSerializer):
    """
    Serializer for security notification logs (read‑only for admins).
    """
    class Meta:
        model = SecurityNotificationLog
        fields = [
            'id', 'notification_type', 'recipient',
            'subject', 'body_preview', 'sent_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class CodeBlacklistSerializer(serializers.ModelSerializer):
    """
    Serializer for code blacklist entries.
    """
    class Meta:
        model = CodeBlacklist
        fields = [
            'id', 'code_hash', 'reason', 'blacklisted_at',
            'expires_at', 'active'
        ]
        read_only_fields = ['id', 'blacklisted_at']


# ============================================================================
# NEW SERIALIZER – added without modifying existing code
# ============================================================================

class SecurityLogSerializer(serializers.ModelSerializer):
    """
    Serializer for SecurityLog (from accounts app).
    Used by SuspiciousActivityReportView and AuditLogView.
    """
    actor_email = serializers.EmailField(source='actor.email', read_only=True, default=None)

    class Meta:
        model = SecurityLog
        fields = [
            'id',
            'actor',
            'actor_email',
            'action',
            'target',
            'ip_address',
            'user_agent',
            'created_at',
        ]
        read_only_fields = fields