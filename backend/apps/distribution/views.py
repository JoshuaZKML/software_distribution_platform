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
    """
    List active mirrors (public).
    """
    queryset = Mirror.objects.filter(is_active=True, is_online=True)
    serializer_class = MirrorSerializer
    permission_classes = [permissions.AllowAny]   # Still public, but only active/online mirrors
    throttle_classes = [AnonRateThrottle]         # Add basic rate limiting


class FileDownloadRedirectView(APIView):
    """
    Given a software version ID, return a redirect to the best mirror URL.
    Requires authentication and a valid license for the software.
    """
    permission_classes = [permissions.IsAuthenticated]   # 🔒 Now protected
    throttle_classes = [UserRateThrottle]

    def get(self, request, version_id):
        # 1. Look up CDN file
        try:
            cdn_file = CDNFile.objects.get(software_version_id=version_id)
        except CDNFile.DoesNotExist:
            raise Http404("File not found")

        # 2. (Optional) Validate user has a license for the software
        software = cdn_file.software_version.software
        if not request.user.licenses.filter(software=software, is_active=True).exists():
            return Response(
                {"error": "You do not have an active license for this software."},
                status=status.HTTP_403_FORBIDDEN
            )

        # 3. Find the best available mirror (priority + health)
        mirror_statuses = MirrorFileStatus.objects.filter(
            cdn_file=cdn_file,
            is_synced=True,
            mirror__is_active=True,
            mirror__is_online=True
        ).select_related('mirror').order_by('mirror__priority')

        if not mirror_statuses.exists():
            return Response(
                {"error": "No mirrors currently available."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # 4. Return a redirect to the first (highest priority) mirror
        best = mirror_statuses.first()
        return redirect(best.url)   # HTTP 302 to the file