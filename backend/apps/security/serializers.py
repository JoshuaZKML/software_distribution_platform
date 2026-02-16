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

# Import SecurityLog from accounts app – corrected path
from backend.apps.accounts.models import SecurityLog


class IPBlacklistSerializer(serializers.ModelSerializer):
    """
    Serializer for IP blacklist entries.
    """
    class Meta:
        model = IPBlacklist
        fields = [
            'id', 'ip_address', 'subnet_mask', 'cidr',
            'reason', 'source', 'is_permanent', 'expires_at',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'cidr', 'created_at', 'updated_at']

    def validate_ip_address(self, value):
        """
        Validate that the value is a valid IP address.
        Uses Python's ipaddress module for robust validation.
        """
        try:
            ipaddress.ip_address(value)
        except ValueError as e:
            raise serializers.ValidationError(f"Invalid IP address: {e}")
        return value


class AbuseAttemptSerializer(serializers.ModelSerializer):
    """
    Serializer for abuse attempts (read‑only for admins).
    Exposes only necessary fields; sensitive request data is excluded.
    """
    class Meta:
        model = AbuseAttempt
        fields = [
            'id', 'ip_address', 'user_agent', 'attempt_type',
            'severity', 'action_taken', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AbuseAlertSerializer(serializers.ModelSerializer):
    """
    Serializer for abuse alerts (read‑only for admins).
    """
    class Meta:
        model = AbuseAlert
        fields = [
            'id', 'alert_type', 'title', 'message',
            'acknowledged', 'acknowledged_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SecurityNotificationLogSerializer(serializers.ModelSerializer):
    """
    Serializer for security notification logs (read‑only for admins).
    """
    class Meta:
        model = SecurityNotificationLog
        fields = [
            'id', 'event_hash', 'user', 'risk_level',
            'ip_address', 'recipient_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class CodeBlacklistSerializer(serializers.ModelSerializer):
    """
    Serializer for code blacklist entries.
    """
    class Meta:
        model = CodeBlacklist
        fields = [
            'id', 'activation_code', 'reason', 'source',
            'is_permanent', 'expires_at', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


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