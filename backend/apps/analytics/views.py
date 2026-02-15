import mimetypes
import os
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.conf import settings
from rest_framework import generics, permissions, filters, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from .models import DailyAggregate, ExportJob, CohortAggregate
from .serializers import DailyAggregateSerializer, ExportJobSerializer, CohortAggregateSerializer

# 👇 ADD THESE TWO IMPORTS (drf-spectacular schema annotation)
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes


class DailyAggregateListView(generics.ListAPIView):
    """
    List daily aggregates, most recent first.
    Supports filtering by date range and ordering.
    """
    queryset = DailyAggregate.objects.all().order_by('-date')
    serializer_class = DailyAggregateSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['date']
    ordering_fields = ['date', 'total_users', 'active_users', 'new_users',
                       'total_sales', 'total_orders', 'licenses_activated',
                       'licenses_expired', 'total_usage_events', 'abuse_attempts']
    ordering = ['-date']  # default ordering

    # Optional: use pagination to limit response size
    pagination_class = None  # Can be set to a custom pagination class if needed


class DailyAggregateDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific day's aggregate.
    Accepts primary key or date (via lookup_field customization).
    """
    queryset = DailyAggregate.objects.all()
    serializer_class = DailyAggregateSerializer
    permission_classes = [permissions.IsAdminUser]
    # If you want to allow lookup by date instead of pk, add:
    # lookup_field = 'date'   # and use the date in URL, e.g., /aggregates/2025-03-21/


# ==============================================================================
# EXPORT JOB VIEWS (unchanged)
# ==============================================================================

class ExportJobListView(generics.ListCreateAPIView):
    """
    List all export jobs for the current user (admin sees all).
    Also allows creating a new export job (POST).
    """
    serializer_class = ExportJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'export_type']
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        # During schema generation (drf-spectacular) avoid evaluating request.user
        if getattr(self, "swagger_fake_view", False):
            return ExportJob.objects.none()

        # Admins can see all export jobs; regular users see only their own
        if self.request.user.is_staff or self.request.user.is_superuser:
            return ExportJob.objects.all()
        return ExportJob.objects.filter(created_by=self.request.user)

    def perform_create(self, serializer):
        # Automatically assign the current user as creator
        serializer.save(created_by=self.request.user)


class ExportJobDetailView(generics.RetrieveAPIView):
    """
    Retrieve details of a specific export job.
    """
    queryset = ExportJob.objects.all()
    serializer_class = ExportJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # During schema generation (drf-spectacular) avoid evaluating request.user
        if getattr(self, "swagger_fake_view", False):
            return ExportJob.objects.none()

        # Enforce row-level security: users can only see their own exports,
        # admins can see all.
        if self.request.user.is_staff or self.request.user.is_superuser:
            return ExportJob.objects.all()
        return ExportJob.objects.filter(created_by=self.request.user)


# 👇 ADDED @extend_schema DECORATOR to document the response
@extend_schema(
    description="Securely download the exported file. Returns either the file (binary) or a JSON with a download URL when using S3.",
    responses={
        200: OpenApiTypes.BINARY,            # for local file download
        200: OpenApiTypes.OBJECT,            # for S3 signed URL response (download_url)
        403: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT,
        500: OpenApiTypes.OBJECT,
    }
)
class ExportJobDownloadView(APIView):
    """
    Securely download the exported file.
    For local storage, serves the file directly; for S3, redirects to a signed URL.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        export_job = get_object_or_404(ExportJob, pk=pk)

        # Permission check: must be owner or admin
        if not (request.user.is_staff or request.user.is_superuser or export_job.created_by == request.user):
            return Response({"detail": "You do not have permission to download this file."},
                            status=status.HTTP_403_FORBIDDEN)

        if export_job.status != 'completed' or not export_job.file:
            return Response({"detail": "File not available or export not completed."},
                            status=status.HTTP_404_NOT_FOUND)

        # --- S3 Private Storage ---
        # If using S3 with private files (AWS_QUERYSTRING_AUTH=True), we redirect to the signed URL.
        if hasattr(settings, 'AWS_STORAGE_BUCKET_NAME') and settings.AWS_STORAGE_BUCKET_NAME:
            try:
                signed_url = export_job.file.url  # This generates a signed URL automatically
                return Response({"download_url": signed_url}, status=status.HTTP_200_OK)
            except Exception as e:
                # Log error and fall through to local handling if needed
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to generate signed URL for export {pk}: {e}")
                return Response({"detail": "Error generating download link."},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- Local Storage (Development) ---
        file_path = export_job.file.path
        if not os.path.exists(file_path):
            return Response({"detail": "File not found on server."},
                            status=status.HTTP_404_NOT_FOUND)

        # Guess content type
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = 'application/octet-stream'

        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response


# ==============================================================================
# COHORT AGGREGATE VIEWS (new, non‑disruptive)
# ==============================================================================

class CohortAggregateListView(generics.ListAPIView):
    """
    List cohort aggregates, most recent first.
    Supports filtering by cohort_date, period, and period_number.
    """
    queryset = CohortAggregate.objects.all()
    serializer_class = CohortAggregateSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['cohort_date', 'period', 'period_number']
    ordering_fields = ['cohort_date', 'period_number']
    ordering = ['-cohort_date', 'period_number']
    pagination_class = None  # Adjust if you want pagination; for large datasets, consider setting a page size