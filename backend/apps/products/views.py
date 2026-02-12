# backend/apps/products/views.py
# =============================================================================
# CORRECTED – FULLY ALIGNED WITH VERIFIED INSTRUCTION
# =============================================================================

from rest_framework import viewsets, generics, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.utils import timezone
from django.db import transaction
import os

from .models import Category, Software, SoftwareVersion, SoftwareImage, SoftwareDocument
from .serializers import (
    CategorySerializer,
    SoftwareSerializer,
    SoftwareVersionSerializer,
    SoftwareImageSerializer,
    SoftwareDocumentSerializer,
)
from backend.apps.accounts.permissions import IsAdmin
from backend.apps.accounts.utils.device_fingerprint import DeviceFingerprintGenerator  # kept for consistency (unused here)


class CategoryViewSet(viewsets.ModelViewSet):
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

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    def perform_destroy(self, instance):
        if instance.software.exists():
            default_category, _ = Category.objects.get_or_create(
                name='Uncategorized',
                slug='uncategorized',
                defaults={'description': 'Uncategorized software'}
            )
            instance.software.update(category=default_category)
        instance.delete()


class SoftwareViewSet(viewsets.ModelViewSet):
    """
    ViewSet for software products.
    """
    queryset = Software.objects.all().select_related('category').prefetch_related(
        'versions', 'images', 'documents'
    ).order_by('display_order', 'name')
    serializer_class = SoftwareSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active', 'is_featured', 'is_new', 'license_type', 'has_trial']
    search_fields = ['name', 'short_description', 'full_description', 'app_code', 'slug']
    ordering_fields = ['name', 'base_price', 'download_count', 'average_rating', 'released_at', 'created_at']
    ordering = ['display_order', 'name']
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated or self.request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            queryset = queryset.filter(is_active=True)

        category_slug = self.request.query_params.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(base_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(base_price__lte=max_price)

        os_filter = self.request.query_params.get('os')
        if os_filter:
            queryset = queryset.filter(versions__supported_os__contains=[os_filter])

        return queryset.distinct()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

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


class SoftwareVersionViewSet(viewsets.ModelViewSet):
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
        if not self.request.user.is_authenticated or self.request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            queryset = queryset.filter(is_active=True)

        software_slug = self.request.query_params.get('software')
        if software_slug:
            queryset = queryset.filter(software__slug=software_slug)
        return queryset

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        software = serializer.validated_data['software']
        if self.request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have permission to add versions to this software.")

        version = serializer.save()
        software.updated_at = timezone.now()
        software.save()

        from backend.apps.accounts.models import SecurityLog
        SecurityLog.objects.create(
            actor=self.request.user,
            action='SOFTWARE_VERSION_ADDED',
            target=f"software:{software.id}/version:{version.id}",
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT'),
            metadata={
                'software_name': software.name,
                'version_number': version.version_number
            }
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


class SoftwareImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for software images.
    """
    queryset = SoftwareImage.objects.all().order_by('display_order')
    serializer_class = SoftwareImageSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        software_slug = self.request.query_params.get('software')
        if software_slug:
            queryset = queryset.filter(software__slug=software_slug)
        return queryset


class SoftwareDocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for software documents.
    """
    queryset = SoftwareDocument.objects.all()
    serializer_class = SoftwareDocumentSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def download(self, request, pk=None):
        document = self.get_object()
        document.download_count += 1
        document.save()
        if document.file:
            response = FileResponse(document.file.open('rb'), as_attachment=True)
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(document.file.name)}"'
            return response
        raise Http404("File not found")


class FeaturedSoftwareView(generics.ListAPIView):
    """
    Get featured software.
    """
    queryset = Software.objects.filter(is_active=True, is_featured=True).order_by('display_order')
    serializer_class = SoftwareSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset()[:10]


class NewReleasesView(generics.ListAPIView):
    """
    Get new software releases.
    """
    queryset = Software.objects.filter(is_active=True, is_new=True).order_by('-released_at')
    serializer_class = SoftwareSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_releases = Software.objects.filter(
            is_active=True,
            released_at__gte=thirty_days_ago
        ).exclude(is_new=True)
        return (queryset | recent_releases).distinct().order_by('-released_at')


class SoftwareDownloadView(generics.GenericAPIView):
    """
    Download software with security checks.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, version_id=None):
        from django.conf import settings
        import hashlib

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
        if token:
            expected_token = hashlib.sha256(
                f"{software.id}|{version.id}|{settings.SECRET_KEY}".encode()
            ).hexdigest()[:32]
            if token != expected_token:
                return Response({
                    'error': 'Invalid download token'
                }, status=status.HTTP_403_FORBIDDEN)

        # Increment counts atomically
        with transaction.atomic():
            software.increment_download_count()
            version.download_count += 1
            version.save()

        from backend.apps.accounts.models import SecurityLog
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

        if version.binary_file:
            response = FileResponse(version.binary_file.open('rb'), as_attachment=True)
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(version.binary_file.name)}"'
            content_types = {
                '.exe': 'application/x-msdownload',
                '.msi': 'application/x-msi',
                '.dmg': 'application/x-apple-diskimage',
                '.pkg': 'application/x-newton-compatible-pkg',
                '.deb': 'application/x-debian-package',
                '.rpm': 'application/x-rpm',
                '.zip': 'application/zip',
                '.tar.gz': 'application/gzip',
            }
            _, ext = os.path.splitext(version.binary_file.name)
            response['Content-Type'] = content_types.get(ext.lower(), 'application/octet-stream')
            return response

        raise Http404("File not found")


class SoftwareVersionListView(generics.ListAPIView):
    """
    Get all versions for a software.
    """
    serializer_class = SoftwareVersionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        slug = self.kwargs.get('slug')
        software = get_object_or_404(Software, slug=slug, is_active=True)
        queryset = software.versions.filter(is_active=True).order_by('-version_number')

        if not self.request.user.is_authenticated or self.request.user.role not in ['ADMIN', 'SUPER_ADMIN']:
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
                'current_version': software.get_latest_version(include_beta=False).version_number if software.get_latest_version(include_beta=False) else None
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