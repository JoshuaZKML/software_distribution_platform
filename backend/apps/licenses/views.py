# FILE: /backend/apps/licenses/views.py
from rest_framework import viewsets, generics, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Sum
import logging

from .models import (
    ActivationCode,
    ActivationLog,
    LicenseFeature,
    CodeBatch,
    LicenseUsage,
    RevocationLog,
)
from .serializers import (
    ActivationCodeSerializer,
    ActivationRequestSerializer,
    ActivationResponseSerializer,
    ValidateActivationSerializer,
    DeactivationRequestSerializer,
    RevocationRequestSerializer,
    LicenseFeatureSerializer,
    CodeBatchSerializer,
    ActivationLogSerializer,
    LicenseUsageSerializer,
    RevocationLogSerializer,
)
from backend.apps.accounts.permissions import IsAdmin, IsSuperAdmin
from backend.apps.accounts.utils.device_fingerprint import DeviceFingerprintGenerator
# The following import has been moved inside the RevokeLicenseView.post method
# to avoid circular imports and startup failure.
# from backend.apps.accounts.tasks import send_license_revocation_email
from backend.apps.products.models import Software

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# ActivationCode ViewSet
# ----------------------------------------------------------------------
class ActivationCodeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for activation codes.
    Users can view their own codes; admins can manage all.
    """
    serializer_class = ActivationCodeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["software", "license_type", "status", "user", "generated_by"]
    search_fields = ["human_code", "notes", "software__name", "software__app_code"]
    ordering_fields = ["created_at", "expires_at", "activated_at", "human_code"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # During schema generation, avoid evaluating request.user or roles
        if getattr(self, "swagger_fake_view", False):
            return ActivationCode.objects.none()

        queryset = ActivationCode.objects.all().select_related(
            "software", "user", "generated_by", "revoked_by", "batch"
        )
        if not self.request.user.is_authenticated:
            return queryset.none()
        if self.request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            queryset = queryset.filter(user=self.request.user)
        software_slug = self.request.query_params.get("software_slug")
        if software_slug:
            queryset = queryset.filter(software__slug=software_slug)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        valid_only = self.request.query_params.get("valid_only", "false").lower() == "true"
        if valid_only:
            queryset = queryset.filter(status="ACTIVATED", expires_at__gt=timezone.now())
        return queryset

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [p() for p in permission_classes]

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def activate_device(self, request, pk=None):
        """Activate this code on a specific device."""
        # Safely retrieve the object – returns 404 if not found
        activation_code = get_object_or_404(ActivationCode, pk=pk)

        # Lock the row for atomic update
        with transaction.atomic():
            activation_code = ActivationCode.objects.select_for_update().get(pk=activation_code.pk)

            # Ownership check
            if activation_code.user != request.user:
                return Response(
                    {"error": "You do not own this activation code."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            device_fingerprint = request.data.get("device_fingerprint")
            if not device_fingerprint:
                device_fingerprint = DeviceFingerprintGenerator.generate(request)

            device_name = request.data.get("device_name", "")
            device_info = request.data.get("device_info", {})

            # Validate activation
            validation = activation_code.validate_for_activation(
                device_fingerprint=device_fingerprint,
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            if not validation["valid"]:
                return Response(
                    {
                        "error": "Cannot activate device",
                        "details": validation["errors"],
                        "warnings": validation["warnings"],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
            )

            if validation["requires_verification"]:
                return Response(
                    {
                        "requires_verification": True,
                        "verification_method": validation["verification_method"],
                        "message": "Device verification required before activation.",
                    },
                    status=status.HTTP_200_OK,
                )

            # Perform activation
            success = activation_code.activate(
                device_fingerprint=device_fingerprint,
                device_name=device_name,
                device_info=device_info,
            )
            if not success:
                return Response(
                    {"error": "Activation failed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Generate encrypted license file (V1.1 with hardware binding)
            license_file = activation_code.get_encrypted_license(include_user_data=True)

            # Get download URL
            download_url = activation_code.software.get_download_url()

            return Response(
                {
                    "success": True,
                    "message": "Device activated successfully.",
                    "activation_id": str(activation_code.id),
                    "license_file": license_file,
                    "download_url": download_url,
                    "device_fingerprint": device_fingerprint,
                    "activation_count": activation_code.activation_count,
                    "remaining_activations": activation_code.remaining_activations,
                },
                status=status.HTTP_200_OK,
            )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def deactivate_device(self, request, pk=None):
        """Deactivate this code from the current device."""
        activation_code = get_object_or_404(ActivationCode, pk=pk)
        if activation_code.user != request.user:
            return Response(
                {"error": "You do not own this activation code."},
                status=status.HTTP_403_FORBIDDEN,
            )

        device_fingerprint = request.data.get("device_fingerprint")
        if not device_fingerprint:
            device_fingerprint = DeviceFingerprintGenerator.generate(request)

        if activation_code.device_fingerprint != device_fingerprint:
            return Response(
                {"error": "This activation code is not active on your current device."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            activation_code.device_fingerprint = None
            activation_code.device_name = ""
            activation_code.device_info = {}
            activation_code.save()

        ActivationLog.objects.create(
            activation_code=activation_code,
            device_fingerprint=device_fingerprint,
            device_name=activation_code.device_name,
            device_info=activation_code.device_info,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT"),
            action="DEACTIVATE",
            success=True,
        )

        return Response(
            {
                "success": True,
                "message": "Device deactivated successfully.",
                "activation_id": str(activation_code.id),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def license_file(self, request, pk=None):
        """Get encrypted license file for this activation code."""
        activation_code = get_object_or_404(ActivationCode, pk=pk)
        if activation_code.user != request.user and request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            return Response(
                {"error": "You do not have permission to access this license."},
                status=status.HTTP_403_FORBIDDEN,
            )
        license_file = activation_code.get_encrypted_license(include_user_data=True)
        return Response(license_file, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def my_licenses(self, request):
        """Get current user's licenses with software details."""
        licenses = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(licenses, many=True, context={"request": request})
        data = serializer.data
        for item, license_obj in zip(data, licenses):
            item["download_url"] = license_obj.software.get_download_url()
        return Response(data, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# GenerateActivationCodeView
# ----------------------------------------------------------------------
class GenerateActivationCodeView(generics.CreateAPIView):
    """Generate new activation codes (admin only)."""
    permission_classes = [IsAdmin]
    serializer_class = ActivationCodeSerializer

    def create(self, request, *args, **kwargs):
        software_slug = request.data.get("software_slug")
        count = int(request.data.get("count", 1))
        license_type = request.data.get("license_type", "STANDARD")
        expires_in_days = int(request.data.get("expires_in_days", 365))
        max_activations = int(request.data.get("max_activations", 1))
        batch_name = request.data.get("batch_name")
        notes = request.data.get("notes", "")

        software = get_object_or_404(Software, slug=software_slug, is_active=True)

        batch = None
        if batch_name:
            batch = CodeBatch.objects.create(
                software=software,
                name=batch_name,
                license_type=license_type,
                count=count,
                max_activations=max_activations,
                expires_in_days=expires_in_days,
                generated_by=request.user,
            )

        with transaction.atomic():
            codes = ActivationCode.generate_for_software(
                software=software,
                count=count,
                license_type=license_type,
                generated_by=request.user,
                expires_in_days=expires_in_days,
                max_activations=max_activations,
                notes=notes,
            )
            if batch:
                batch.used_count = len(codes)
                batch.is_used = True
                batch.save()

        response_data = {
            "success": True,
            "message": f"Successfully generated {len(codes)} activation codes.",
            "codes_generated": len(codes),
            "software": {
                "name": software.name,
                "slug": software.slug,
                "app_code": software.app_code,
            },
            "batch_id": str(batch.id) if batch else None,
            "codes": [
                {
                    "id": str(c.id),
                    "human_code": c.human_code,
                    "license_type": c.license_type,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                    "max_activations": c.max_activations,
                }
                for c in codes
            ],
        }
        return Response(response_data, status=status.HTTP_201_CREATED)


# ----------------------------------------------------------------------
# ValidateActivationCodeView
# ----------------------------------------------------------------------
class ValidateActivationCodeView(generics.GenericAPIView):
    """Validate activation code without activating (public)."""
    permission_classes = [AllowAny]
    serializer_class = ValidateActivationSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code_obj = serializer.validated_data["activation_code_obj"]
        software = serializer.validated_data["software"]
        device_fingerprint = serializer.validated_data.get("device_fingerprint")
        check_only = serializer.validated_data.get("check_only", False)

        validation = code_obj.validate_for_activation(
            device_fingerprint=device_fingerprint,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        response_data = {
            "valid": validation["valid"],
            "can_activate": validation["can_activate"],
            "activation_code": code_obj.human_code,
            "software": {
                "name": software.name,
                "slug": software.slug,
                "app_code": software.app_code,
            },
            "license_type": code_obj.license_type,
            "status": code_obj.status,
            "expires_at": code_obj.expires_at.isoformat() if code_obj.expires_at else None,
            "max_activations": code_obj.max_activations,
            "activation_count": code_obj.activation_count,
            "remaining_activations": code_obj.remaining_activations,
            "requires_verification": validation["requires_verification"],
            "verification_method": validation["verification_method"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        }

        if not check_only:
            ActivationLog.objects.create(
                activation_code=code_obj,
                device_fingerprint=device_fingerprint or "",
                device_name="",
                device_info={},
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
                action="VALIDATE",
                success=validation["valid"],
                error_message="; ".join(validation["errors"]) if not validation["valid"] else "",
            )

        return Response(response_data, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# ActivateLicenseView
# ----------------------------------------------------------------------
class ActivateLicenseView(generics.GenericAPIView):
    """Activate a license for the current user."""
    permission_classes = [IsAuthenticated]
    serializer_class = ActivationRequestSerializer

    def post(self, request):
        with transaction.atomic():
            serializer = self.get_serializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)

            code_obj = serializer.validated_data["activation_code_obj"]
            software = serializer.validated_data["software"]
            device_fingerprint = serializer.validated_data.get("device_fingerprint")
            device_name = serializer.validated_data.get("device_name", "")
            device_info = serializer.validated_data.get("device_info", {})
            force_activation = serializer.validated_data.get("force_activation", False)

            # Lock the row
            code_obj = ActivationCode.objects.select_for_update().get(pk=code_obj.pk)

            # Check assignment
            if code_obj.user and code_obj.user != request.user and not force_activation:
                return Response(
                    {"error": "This activation code is already assigned to another user."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Generate fingerprint if not provided
            if not device_fingerprint:
                device_fingerprint = DeviceFingerprintGenerator.generate(request)

            validation = code_obj.validate_for_activation(
                device_fingerprint=device_fingerprint,
                ip_address=request.META.get("REMOTE_ADDR"),
            )

            if not validation["valid"] and not force_activation:
                return Response(
                    {
                        "error": "Cannot activate license",
                        "details": validation["errors"],
                        "warnings": validation["warnings"],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if validation["requires_verification"] and not force_activation:
                return Response(
                    {
                        "requires_verification": True,
                        "verification_method": validation["verification_method"],
                        "message": "Verification required before activation.",
                    },
                    status=status.HTTP_200_OK,
                )

            # Assign user if not already assigned
            if not code_obj.user:
                code_obj.user = request.user

            # Perform activation
            success = code_obj.activate(
                device_fingerprint=device_fingerprint,
                device_name=device_name,
                device_info=device_info,
            )
            if not success:
                return Response(
                    {"error": "Activation failed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Prepare and return encrypted license file via ActivationResponseSerializer
            response_serializer = ActivationResponseSerializer(
                code_obj,
                context={
                    "request": request,
                    "hardware_id": device_fingerprint,  # ✅ Passed to serializer for V1.1 binding
                },
            )
            return Response(response_serializer.data, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# DeactivateLicenseView
# ----------------------------------------------------------------------
class DeactivateLicenseView(generics.GenericAPIView):
    """Deactivate a license from the current device."""
    permission_classes = [IsAuthenticated]
    serializer_class = DeactivationRequestSerializer

    def post(self, request):
        with transaction.atomic():
            serializer = self.get_serializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)

            code = serializer.validated_data["activation_code"]
            reason = serializer.validated_data.get("reason", "")
            keep_license = serializer.validated_data.get("keep_license", False)

            # Lock the row
            code = ActivationCode.objects.select_for_update().get(pk=code.pk)

            # Deactivate device
            code.device_fingerprint = None
            code.device_name = ""
            code.device_info = {}

            if not keep_license:
                code.user = None
                code.activation_count = max(0, code.activation_count - 1)

            code.save()

            ActivationLog.objects.create(
                activation_code=code,
                device_fingerprint=code.device_fingerprint,
                device_name=code.device_name,
                device_info=code.device_info,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
                action="DEACTIVATE",
                success=True,
            )

            return Response(
                {
                    "success": True,
                    "message": "License deactivated successfully.",
                    "activation_id": str(code.id),
                    "keep_license": keep_license,
                },
                status=status.HTTP_200_OK,
            )


# ----------------------------------------------------------------------
# RevokeLicenseView
# ----------------------------------------------------------------------
class RevokeLicenseView(generics.GenericAPIView):
    """Revoke a license (admin only)."""
    permission_classes = [IsAdmin]
    serializer_class = RevocationRequestSerializer

    def post(self, request, code_id=None):
        if code_id:
            code = get_object_or_404(ActivationCode, id=code_id)
        else:
            serializer = self.get_serializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            code = serializer.validated_data["activation_code"]

        reason = request.data.get("reason", "Administrative revocation")
        notify_user = request.data.get("notify_user", True)

        with transaction.atomic():
            success = code.revoke(revoked_by=request.user, reason=reason)
            if not success:
                return Response(
                    {"error": "Revocation failed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if notify_user and code.user:
            # Local import to avoid circular dependency at startup
            from backend.apps.accounts.tasks import send_license_revocation_email
            send_license_revocation_email.delay(
                user_id=code.user.id,
                activation_code=code.human_code,
                software_name=code.software.name,
                reason=reason,
            )

        return Response(
            {
                "success": True,
                "message": "License revoked successfully.",
                "activation_id": str(code.id),
                "revoked_by": request.user.email,
                "revoked_at": timezone.now().isoformat(),
                "reason": reason,
            },
            status=status.HTTP_200_OK,
        )


# ----------------------------------------------------------------------
# UserLicensesView
# ----------------------------------------------------------------------
class UserLicensesView(generics.ListAPIView):
    """Get all licenses for the current user."""
    permission_classes = [IsAuthenticated]
    serializer_class = ActivationCodeSerializer

    def get_queryset(self):
        # During schema generation, return empty queryset to avoid accessing user
        if getattr(self, "swagger_fake_view", False):
            return ActivationCode.objects.none()

        return ActivationCode.objects.filter(user=self.request.user).select_related(
            "software", "software_version"
        ).order_by("-created_at")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        licenses_by_software = {}
        for lic in queryset:
            slug = lic.software.slug
            if slug not in licenses_by_software:
                licenses_by_software[slug] = {
                    "software": {
                        "name": lic.software.name,
                        "slug": lic.software.slug,
                        "app_code": lic.software.app_code,
                        "description": lic.software.short_description,
                        "download_url": lic.software.get_download_url(),
                    },
                    "licenses": [],
                }
            licenses_by_software[slug]["licenses"].append(self.get_serializer(lic).data)

        summary = {
            "total_licenses": queryset.count(),
            "active_licenses": queryset.filter(
                status="ACTIVATED", expires_at__gt=timezone.now()
            ).count(),
            "software_count": len(licenses_by_software),
            "expiring_soon": queryset.filter(
                status="ACTIVATED",
                expires_at__gt=timezone.now(),
                expires_at__lte=timezone.now() + timezone.timedelta(days=30),
            ).count(),
        }
        return Response(
            {"summary": summary, "licenses_by_software": list(licenses_by_software.values())},
            status=status.HTTP_200_OK,
        )


# ----------------------------------------------------------------------
# CheckForUpdatesView
# ----------------------------------------------------------------------
class CheckForUpdatesView(generics.GenericAPIView):
    """Check for software updates for user's licenses."""
    permission_classes = [IsAuthenticated]

    def get(self, request, software_slug):
        software = get_object_or_404(Software, slug=software_slug, is_active=True)
        user_license = ActivationCode.objects.filter(
            user=request.user,
            software=software,
            status="ACTIVATED",
            expires_at__gt=timezone.now(),
        ).first()

        if not user_license:
            return Response(
                {"error": "You do not have an active license for this software."},
                status=status.HTTP_403_FORBIDDEN,
            )

        current_version = user_license.software_version or software.get_latest_version(include_beta=False)
        from backend.apps.products.serializers import SoftwareVersionSerializer

        available_updates = software.versions.filter(
            is_active=True,
            is_stable=True,
            released_at__gt=current_version.released_at if current_version else timezone.now(),
        ).order_by("-released_at")

        update_serializer = SoftwareVersionSerializer(
            available_updates, many=True, context={"request": request}
        )

        return Response(
            {
                "software": {
                    "name": software.name,
                    "slug": software.slug,
                    "current_version": SoftwareVersionSerializer(
                        current_version, context={"request": request}
                    ).data if current_version else None,
                },
                "updates_available": available_updates.count(),
                "updates": update_serializer.data,
                "license_valid": user_license.is_valid,
                "license_type": user_license.license_type,
            },
            status=status.HTTP_200_OK,
        )


# ----------------------------------------------------------------------
# LicenseFeature ViewSet
# ----------------------------------------------------------------------
class LicenseFeatureViewSet(viewsets.ModelViewSet):
    """ViewSet for license features (read‑only for users)."""
    queryset = LicenseFeature.objects.all().order_by("display_order", "name")
    serializer_class = LicenseFeatureSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["software", "is_active"]
    search_fields = ["name", "code", "description"]

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAdmin]
        else:
            permission_classes = [AllowAny]
        return [p() for p in permission_classes]

    def get_queryset(self):
        # During schema generation, avoid evaluating request.user.role
        if getattr(self, "swagger_fake_view", False):
            return LicenseFeature.objects.none()

        qs = super().get_queryset()
        if self.request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            qs = qs.filter(is_active=True)
        software_slug = self.request.query_params.get("software")
        if software_slug:
            qs = qs.filter(software__slug=software_slug)
        return qs


# ----------------------------------------------------------------------
# CodeBatch ViewSet
# ----------------------------------------------------------------------
class CodeBatchViewSet(viewsets.ModelViewSet):
    """ViewSet for code batches (admin only)."""
    queryset = CodeBatch.objects.all().order_by("-created_at")
    serializer_class = CodeBatchSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["software", "license_type", "is_used"]
    search_fields = ["name", "description", "software__name"]

    @action(detail=True, methods=["get"])
    def codes(self, request, pk=None):
        batch = self.get_object()
        # Approximate matching within 5 minutes of batch creation
        codes = ActivationCode.objects.filter(
            software=batch.software,
            generated_by=batch.generated_by,
            created_at__gte=batch.created_at - timezone.timedelta(minutes=5),
            created_at__lte=batch.created_at + timezone.timedelta(minutes=5),
        )
        page = self.paginate_queryset(codes)
        if page:
            serializer = ActivationCodeSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = ActivationCodeSerializer(codes, many=True, context={"request": request})
        return Response(serializer.data)


# ----------------------------------------------------------------------
# ActivationLog ViewSet
# ----------------------------------------------------------------------
class ActivationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for activation logs (users see own, admins see all)."""
    queryset = ActivationLog.objects.all().order_by("-created_at")
    serializer_class = ActivationLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["activation_code", "action", "success", "is_suspicious"]
    search_fields = ["activation_code__human_code", "device_fingerprint", "ip_address"]

    def get_queryset(self):
        # During schema generation, avoid evaluating request.user.role
        if getattr(self, "swagger_fake_view", False):
            return ActivationLog.objects.none()

        qs = super().get_queryset()
        if self.request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            qs = qs.filter(activation_code__user=self.request.user)
        return qs


# ----------------------------------------------------------------------
# LicenseUsage ViewSet
# ----------------------------------------------------------------------
class LicenseUsageViewSet(viewsets.ModelViewSet):
    """ViewSet for license usage tracking."""
    queryset = LicenseUsage.objects.all().order_by("-created_at")
    serializer_class = LicenseUsageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["activation_code", "feature", "device_fingerprint"]

    def get_queryset(self):
        # During schema generation, avoid evaluating request.user.role
        if getattr(self, "swagger_fake_view", False):
            return LicenseUsage.objects.none()

        qs = super().get_queryset()
        if self.request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            qs = qs.filter(activation_code__user=self.request.user)
        return qs

    @action(detail=False, methods=["post"])
    def log_usage(self, request):
        activation_code_id = request.data.get("activation_code_id")
        feature_code = request.data.get("feature_code")
        usage_data = request.data.get("usage_data", {})

        if not activation_code_id or not feature_code:
            return Response(
                {"error": "activation_code_id and feature_code are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = get_object_or_404(
            ActivationCode,
            id=activation_code_id,
            user=request.user,
        )
        feature = get_object_or_404(
            LicenseFeature,
            code=feature_code,
            software=code.software,
        )

        if not feature.is_available_for_license_type(code.license_type):
            return Response(
                {"error": f"Feature '{feature_code}' is not available for {code.license_type} license."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if feature.max_usage:
            total = LicenseUsage.objects.filter(
                activation_code=code, feature=feature
            ).aggregate(total=Sum("usage_count"))["total"] or 0
            if total >= feature.max_usage:
                return Response(
                    {"error": f"Usage limit reached for feature '{feature_code}'."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        device_fingerprint = DeviceFingerprintGenerator.generate(request)
        usage = LicenseUsage.objects.create(
            activation_code=code,
            feature=feature,
            usage_count=1,
            usage_data=usage_data,
            device_fingerprint=device_fingerprint,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return Response(
            {
                "success": True,
                "message": "Usage logged successfully.",
                "usage_id": str(usage.id),
                "feature": feature.name,
                "total_usage": total + 1 if feature.max_usage else "unlimited",
            },
            status=status.HTTP_201_CREATED,
        )


# ----------------------------------------------------------------------
# Offline License Validation
# ----------------------------------------------------------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def validate_offline_license(request):
    """Validate offline license file."""
    license_file = request.FILES.get("license_file")
    software_slug = request.data.get("software_slug")

    if not license_file or not software_slug:
        return Response(
            {"error": "license_file and software_slug are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        license_content = license_file.read().decode("utf-8")
    except Exception as e:
        return Response(
            {"error": f"Failed to read license file: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from .utils.encryption import LicenseEncryptionManager

    manager = LicenseEncryptionManager()
    validation = manager.validate_license_file(
        license_content,
        current_hardware_id=DeviceFingerprintGenerator.generate(request),
    )

    if not validation["valid"]:
        return Response(
            {"valid": False, "error": validation["error"]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    license_data = validation["data"]
    if license_data.get("software", {}).get("slug") != software_slug:
        return Response(
            {
                "valid": False,
                "error": f'License is for software "{license_data["software"]["slug"]}", not "{software_slug}".',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user_id_from_license = license_data.get("user", {}).get("id")
    if user_id_from_license and user_id_from_license != str(request.user.id):
        return Response(
            {"valid": False, "error": "License is assigned to another user."},
            status=status.HTTP_403_FORBIDDEN,
        )

    return Response(
        {"valid": True, "license_data": license_data, "message": "License is valid."},
        status=status.HTTP_200_OK,
    )