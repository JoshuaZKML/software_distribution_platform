# FILE: backend/apps/api/serializers.py
from rest_framework import serializers
from backend.apps.products.models import Software


class PublicCatalogSerializer(serializers.ModelSerializer):
    """
    Serializer for public software catalog.
    Exposes only non‑sensitive, public information.
    """
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Software
        fields = [
            'id',
            'name',
            'slug',
            'app_code',
            'short_description',
            'icon_url',
            'download_url',
            'version',
            'created_at',
        ]
        read_only_fields = fields

    def get_download_url(self, obj):
        # Use the model's method if available, otherwise construct a simple URL
        if hasattr(obj, 'get_download_url'):
            return obj.get_download_url()
        # Fallback: return a placeholder or None
        return None


class SystemHealthSerializer(serializers.Serializer):
    """
    Serializer for system health response.
    """
    database = serializers.CharField()
    cache = serializers.CharField()
    celery = serializers.CharField()
    timestamp = serializers.FloatField()


class SystemMetricsSerializer(serializers.Serializer):
    """
    Serializer for system metrics.
    """
    requests_per_minute = serializers.IntegerField()
    active_users = serializers.IntegerField()
    total_licenses_activated = serializers.IntegerField()
    uptime_seconds = serializers.IntegerField()


class SystemConfigSerializer(serializers.Serializer):
    """
    Serializer for system configuration (safe values only).
    """
    debug = serializers.BooleanField()
    api_version = serializers.CharField()
    allowed_hosts = serializers.ListField(child=serializers.CharField())
    csrf_trusted_origins = serializers.ListField(child=serializers.CharField())
    session_cookie_age = serializers.IntegerField()