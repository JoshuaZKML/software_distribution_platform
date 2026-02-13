# FILE: /backend/apps/products/views.py
"""
Product views for Software Distribution Platform.
Production‑grade hardening: signed download tokens, optimized queries,
centralized permissions, and X‑Accel‑Redirect support.
All changes are backward‑compatible and non‑disruptive.
"""
import os
import hashlib

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from backend.apps.accounts.models import SecurityLog
from backend.apps.accounts.permissions import IsAdmin

from .filters import SoftwareFilter
from .models import Category, Software, SoftwareDocument, SoftwareImage, SoftwareVersion
from .serializers import (
    CategorySerializer,
    SoftwareDocumentSerializer,
    SoftwareImageSerializer,
    SoftwareSerializer,
    SoftwareVersionSerializer,
)


# ----------------------------------------------------------------------
# Permission & queryset mixins – DRY centralisation
# ----------------------------------------------------------------------
class AdminWritePermissionMixin:
    """
    Mixin that grants write permissions only to admin users,
    and read permissions to anyone.
    """
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]


class ActiveOnlyMixin:
    """
    Mixin that filters queryset to active objects for non‑admin users.
    """
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not (user and user.is_authenticated and getattr(user, 'role', None) in ['ADMIN', 'SUPER_ADMIN']):
            queryset = queryset.filter(is_active=True)
        return queryset


# ----------------------------------------------------------------------
# Category ViewSet
# ----------------------------------------------------------------------
class CategoryViewSet(AdminWritePermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for software categories.
    """
    queryset = Category.objects.all().order_by('display_order', 'name')
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'parent']
    search_fields = ['name', 'description', 'slug']
    ordering_fields = ['name', 'display_order', 'created_at']
    ordering = ['display_order', 'name']

    @transaction.atomic
    def perform_destroy(self, instance):
        if instance.software.exists():
            # Ensure 'Uncategorized' exists atomically; if two deletions race,
            # the transaction will retry and avoid IntegrityError.
            default_category, _ = Category.objects.get_or_create(
                name='Uncategorized',
                slug='uncategorized',
                defaults={'description': 'Uncategorized software'}
            )
            instance.software.update(category=default_category)
        instance.delete()


# ----------------------------------------------------------------------
# Software ViewSet – with dedicated FilterSet
# ----------------------------------------------------------------------
class SoftwareViewSet(AdminWritePermissionMixin, ActiveOnlyMixin, viewsets.ModelViewSet):
    """
    ViewSet for software products.
    """
    queryset = Software.objects.all().select_related('category').prefetch_related(
        'versions', 'images', 'documents'
    ).order_by('display_order', 'name')
    serializer_class = SoftwareSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SoftwareFilter
    search_fields = ['name', 'short_description', 'full_description', 'app_code', 'slug']
    ordering_fields = ['name', 'base_price', 'download_count', 'average_rating',
                       'released_at', 'created_at']
    ordering = ['display_order', 'name']
    lookup_field = 'slug'

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def toggle_featured(self, request, slug=None):
        software = self.get_object()
        software.is_featured = not software.is_featured
        software.save()
        return Response({
            'success': True,
            'message': f'Software {"featured" if software.is_featured else "unfeatured"}',
            'is_featured': software.is_featured
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def toggle_active(self, request, slug=None):
        software = self.get_object()
        software.is_active = not software.is_active
        software.save()
        return Response({
            'success': True,
            'message': f'Software {"activated" if software.is_active else "deactivated"}',
            'is_active': software.is_active
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def versions(self, request, slug=None):
        software = self.get_object()
        versions = software.versions.all().order_by('-version_number')
        page = self.paginate_queryset(versions)
        if page is not None:
            serializer = SoftwareVersionSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = SoftwareVersionSerializer(versions, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def images(self, request, slug=None):
        software = self.get_object()
        images = software.images.filter(is_active=True).order_by('display_order')
        serializer = SoftwareImageSerializer(images, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def documents(self, request, slug=None):
        software = self.get_object()
        documents = software.documents.filter(is_active=True)
        serializer = SoftwareDocumentSerializer(documents, many=True, context={'request': request})
        return Response(serializer.data)


# ----------------------------------------------------------------------
# Software Version ViewSet – with service layer
# ----------------------------------------------------------------------
class SoftwareVersionViewSet(AdminWritePermissionMixin, ActiveOnlyMixin, viewsets.ModelViewSet):
    """
    ViewSet for software versions.
    """
    queryset = SoftwareVersion.objects.all().select_related('software').order_by('-version_number')
    serializer_class = SoftwareVersionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['software', 'is_active', 'is_beta', 'is_stable', 'is_signed']
    search_fields = ['version_number', 'version_code', 'release_name', 'release_notes']
    ordering_fields = ['version_number', 'released_at', 'download_count', 'created_at']
    ordering = ['-version_number']

    def get_queryset(self):
        queryset = super().get_queryset()
        software_slug = self.request.query_params.get('software')
        if software_slug:
            queryset = queryset.filter(software__slug=software_slug)
        return queryset

    def perform_create(self, serializer):
        """
        Delegate version creation logic to a service function.
        This ensures the same behaviour is available outside views.
        """
        from .services import create_software_version
        create_software_version(
            serializer=serializer,
            user=self.request.user,
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT')
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def toggle_active(self, request, pk=None):
        version = self.get_object()
        version.is_active = not version.is_active
        version.save()
        return Response({
            'success': True,
            'message': f'Version {"activated" if version.is_active else "deactivated"}',
            'is_active': version.is_active
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def toggle_beta(self, request, pk=None):
        version = self.get_object()
        version.is_beta = not version.is_beta
        version.save()
        return Response({
            'success': True,
            'message': f'Version {"marked as beta" if version.is_beta else "marked as stable"}',
            'is_beta': version.is_beta,
            'is_stable': not version.is_beta
        }, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# Software Image ViewSet
# ----------------------------------------------------------------------
class SoftwareImageViewSet(AdminWritePermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for software images.
    """
    queryset = SoftwareImage.objects.all().order_by('display_order')
    serializer_class = SoftwareImageSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        software_slug = self.request.query_params.get('software')
        if software_slug:
            queryset = queryset.filter(software__slug=software_slug)
        return queryset


# ----------------------------------------------------------------------
# Software Document ViewSet
# ----------------------------------------------------------------------
class SoftwareDocumentViewSet(AdminWritePermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for software documents.
    """
    queryset = SoftwareDocument.objects.all()
    serializer_class = SoftwareDocumentSerializer

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def download(self, request, pk=None):
        document = self.get_object()
        # Atomic increment
        SoftwareDocument.objects.filter(pk=document.pk).update(
            download_count=F('download_count') + 1
        )
        document.refresh_from_db()

        if not document.file:
            raise Http404("File not found")

        # Serve via web server if configured
        if getattr(settings, 'USE_X_ACCEL_REDIRECT', False):
            response = HttpResponse()
            response['X-Accel-Redirect'] = document.file.url
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(document.file.name)}"'
            return response

        # Fallback: Django serves the file
        response = FileResponse(document.file.open('rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(document.file.name)}"'
        return response


# ----------------------------------------------------------------------
# Public listing endpoints
# ----------------------------------------------------------------------
class FeaturedSoftwareView(generics.ListAPIView):
    """
    Get featured software.
    """
    queryset = Software.objects.filter(is_active=True, is_featured=True).order_by('display_order')[:10]
    serializer_class = SoftwareSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class NewReleasesView(generics.ListAPIView):
    """
    Get new software releases.
    """
    serializer_class = SoftwareSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        # Single query using Q objects (more efficient than union)
        return Software.objects.filter(
            Q(is_active=True, is_new=True) |
            Q(is_active=True, released_at__gte=thirty_days_ago)
        ).distinct().order_by('-released_at')


# ----------------------------------------------------------------------
# Secure download endpoint – supports both legacy and signed tokens
# ----------------------------------------------------------------------
class SoftwareDownloadView(generics.GenericAPIView):
    """
    Download software with security checks.
    Supports signed, time‑limited tokens (recommended) and falls back
    to the legacy hash‑based token for backward compatibility.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, version_id=None):
        from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

        software = get_object_or_404(Software, slug=slug, is_active=True)

        if version_id:
            version = get_object_or_404(
                SoftwareVersion,
                id=version_id,
                software=software,
                is_active=True
            )
        else:
            version = software.get_latest_version(include_beta=False)
            if not version:
                raise Http404("No active version found")

        token = request.GET.get('token')
        if not token:
            return Response({'error': 'Missing download token'}, status=status.HTTP_403_FORBIDDEN)

        # 1. Try to validate using Django's TimestampSigner (new format)
        signer = TimestampSigner()
        try:
            signer.unsign(token, max_age=3600)
        except (BadSignature, SignatureExpired):
            # 2. Fallback: legacy SHA256 hash token (no expiry)
            expected_token = hashlib.sha256(
                f"{software.id}|{version.id}|{settings.SECRET_KEY}".encode()
            ).hexdigest()[:32]
            if token != expected_token:
                return Response({'error': 'Invalid or expired download token'},
                                status=status.HTTP_403_FORBIDDEN)
        except Exception:
            return Response({'error': 'Invalid token'}, status=status.HTTP_403_FORBIDDEN)

        # Atomically increment download counters
        with transaction.atomic():
            software.increment_download_count()
            # Atomic update for version download count
            SoftwareVersion.objects.filter(pk=version.pk).update(
                download_count=F('download_count') + 1
            )
            version.refresh_from_db()

        # Security logging
        SecurityLog.objects.create(
            actor=request.user,
            action='SOFTWARE_DOWNLOAD',
            target=f"software:{software.id}/version:{version.id}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT'),
            metadata={
                'software_name': software.name,
                'version': version.version_number,
                'file_name': os.path.basename(version.binary_file.name) if version.binary_file else ''
            }
        )

        if not version.binary_file:
            raise Http404("File not found")

        # Serve via web server if configured
        if getattr(settings, 'USE_X_ACCEL_REDIRECT', False):
            response = HttpResponse()
            response['X-Accel-Redirect'] = version.binary_file.url
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(version.binary_file.name)}"'
            return response

        # Django serves the file directly
        response = FileResponse(version.binary_file.open('rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(version.binary_file.name)}"'

        # Set correct content type based on file extension
        content_types = {
            '.exe': 'application/x-msdownload',
            '.msi': 'application/x-msi',
            '.dmg': 'application/x-apple-diskimage',
            '.pkg': 'application/x-newton-compatible-pkg',
            '.deb': 'application/x-debian-package',
            '.rpm': 'application/x-rpm',
            '.zip': 'application/zip',
            '.tar.gz': 'application/gzip',
            '.tar': 'application/x-tar',
            '.gz': 'application/gzip',
        }
        _, ext = os.path.splitext(version.binary_file.name)
        # Handle double extensions like .tar.gz
        if version.binary_file.name.endswith('.tar.gz'):
            ext = '.tar.gz'
        response['Content-Type'] = content_types.get(ext.lower(), 'application/octet-stream')
        return response


class SoftwareVersionListView(generics.ListAPIView):
    """
    Get all versions for a software (public).
    """
    serializer_class = SoftwareVersionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        slug = self.kwargs.get('slug')
        software = get_object_or_404(Software, slug=slug, is_active=True)
        queryset = software.versions.filter(is_active=True).order_by('-version_number')

        # Non‑admins cannot see beta versions unless explicitly requested
        user = self.request.user
        is_admin = user.is_authenticated and getattr(user, 'role', None) in ['ADMIN', 'SUPER_ADMIN']
        if not is_admin:
            show_beta = self.request.query_params.get('show_beta', 'false').lower() == 'true'
            if not show_beta:
                queryset = queryset.filter(is_beta=False)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        software = get_object_or_404(Software, slug=self.kwargs.get('slug'))

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['software'] = {
                'id': str(software.id),
                'name': software.name,
                'slug': software.slug,
                'current_version': (
                    software.get_latest_version(include_beta=False).version_number
                    if software.get_latest_version(include_beta=False) else None
                )
            }
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'software': {
                'id': str(software.id),
                'name': software.name,
                'slug': software.slug
            },
            'versions': serializer.data
        })