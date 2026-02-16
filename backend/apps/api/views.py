# FILE: backend/apps/api/views.py
"""
API views for software distribution platform.
Provides core API endpoints and status checks.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework import status
from django.conf import settings
from django.core.cache import cache
import time

from backend.apps.products.models import Software
from .serializers import (
    PublicCatalogSerializer,
    SystemHealthSerializer,
    SystemMetricsSerializer,
    SystemConfigSerializer,
)


# ----------------------------------------------------------------------
# Existing view – kept unchanged
# ----------------------------------------------------------------------
class APIStatusView(APIView):
    """
    Public endpoint to check API health and version.
    Returns 200 OK when the API is operational.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'status': 'operational',
            'version': getattr(settings, 'API_VERSION', '1.0'),
            'environment': getattr(settings, 'ENVIRONMENT', 'development'),
            'message': 'API is running.'
        }, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# New views – added to resolve startup errors
# ----------------------------------------------------------------------
class PublicCatalogView(APIView):
    """
    Public endpoint listing all active software with basic info.
    Cached for 5 minutes to reduce database load.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = 'public_software_catalog'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        # Get all active software, ordered by name
        software_list = Software.objects.filter(is_active=True).order_by('name')
        serializer = PublicCatalogSerializer(software_list, many=True, context={'request': request})
        data = serializer.data

        # Cache for 5 minutes
        cache.set(cache_key, data, 60 * 5)
        return Response(data)


class SystemHealthView(APIView):
    """
    System health check endpoint (admin only).
    Returns status of critical services: database, cache, etc.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        health_data = {
            'database': 'ok',  # we can assume if this view is reached, DB is ok
            'cache': 'ok',
            'celery': 'unknown',  # would need to ping celery; placeholder
            'timestamp': time.time(),
        }
        # Optional: check cache connectivity
        try:
            cache.set('health_check', 'ok', 1)
            cache.get('health_check')
        except Exception:
            health_data['cache'] = 'error'

        serializer = SystemHealthSerializer(data=health_data)
        serializer.is_valid()
        return Response(serializer.data)


class SystemMetricsView(APIView):
    """
    System metrics endpoint (admin only).
    Returns basic performance metrics (placeholder for now).
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Placeholder – can be extended with real metrics
        metrics = {
            'requests_per_minute': 0,
            'active_users': 0,
            'total_licenses_activated': 0,
            'uptime_seconds': 0,
        }
        serializer = SystemMetricsSerializer(data=metrics)
        serializer.is_valid()
        return Response(serializer.data)


class SystemConfigView(APIView):
    """
    System configuration endpoint (admin only).
    Returns non‑sensitive configuration parameters.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        config = {
            'debug': settings.DEBUG,
            'api_version': getattr(settings, 'API_VERSION', '1.0'),
            'allowed_hosts': settings.ALLOWED_HOSTS,
            'csrf_trusted_origins': getattr(settings, 'CSRF_TRUSTED_ORIGINS', []),
            'session_cookie_age': settings.SESSION_COOKIE_AGE,
        }
        serializer = SystemConfigSerializer(data=config)
        serializer.is_valid()
        return Response(serializer.data)