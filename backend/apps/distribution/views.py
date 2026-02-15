# FILE: backend/apps/distribution/views.py
from django.shortcuts import redirect
from django.http import Http404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

from .models import Mirror, CDNFile, MirrorFileStatus
from .serializers import MirrorSerializer


class MirrorListView(generics.ListAPIView):
    """List active mirrors (public)."""
    queryset = Mirror.objects.filter(is_active=True, is_online=True)
    serializer_class = MirrorSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonRateThrottle]


class FileDownloadRedirectView(APIView):
    """
    Redirect to the best mirror for a given software version and artifact type.
    - Simple usage (defaults to 'installer'): /file/<version_id>/
    - Explicit usage: /file/<version_id>/<artifact_type>/
    Requires authentication and a valid license.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request, version_id, artifact_type='installer'):
        # Look up CDN file (unique together: version + artifact_type)
        try:
            cdn_file = CDNFile.objects.select_related(
                'software_version__software'
            ).get(
                software_version_id=version_id,
                artifact_type=artifact_type
            )
        except CDNFile.DoesNotExist:
            raise Http404("File not found")

        # Validate license
        software = cdn_file.software_version.software
        if not request.user.licenses.filter(software=software, is_active=True).exists():
            return Response(
                {"error": "You do not have an active license for this software."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Find best mirror
        best = (
            MirrorFileStatus.objects
            .filter(
                cdn_file=cdn_file,
                is_synced=True,
                mirror__is_active=True,
                mirror__is_online=True
            )
            .select_related('mirror')
            .order_by('mirror__priority', 'mirror__average_latency_ms')
            .first()
        )

        if not best:
            return Response(
                {"error": "No mirrors currently available."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        return redirect(best.url)