# FILE: /backend/apps/licenses/serializers.py
from rest_framework import serializers
from django.utils import timezone
from django.conf import settings          # ✅ ADDED
import hashlib                            # ✅ ADDED
from datetime import timedelta
import base64

from .models import (
    ActivationCode,
    ActivationLog,
    LicenseFeature,
    CodeBatch,
    LicenseUsage,
    RevocationLog,
)
from backend.apps.products.models import Software, SoftwareVersion
from backend.apps.accounts.models import User


# ----------------------------------------------------------------------
# Activation Code Serializer (Full)
# ----------------------------------------------------------------------
class ActivationCodeSerializer(serializers.ModelSerializer):
    software_name = serializers.CharField(source="software.name", read_only=True)
    software_slug = serializers.CharField(source="software.slug", read_only=True)
    software_app_code = serializers.CharField(source="software.app_code", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True, allow_null=True)
    generated_by_email = serializers.EmailField(source="generated_by.email", read_only=True, allow_null=True)
    revoked_by_email = serializers.EmailField(source="revoked_by.email", read_only=True, allow_null=True)
    batch_name = serializers.CharField(source="batch.name", read_only=True, allow_null=True)

    # Computed properties
    is_valid = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_revoked = serializers.BooleanField(read_only=True)
    remaining_activations = serializers.IntegerField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True, allow_null=True)

    # Encrypted license file (optional, generated on demand)
    license_file = serializers.SerializerMethodField()

    class Meta:
        model = ActivationCode
        fields = [
            "id",
            "software",
            "software_name",
            "software_slug",
            "software_app_code",
            "software_version",
            "batch",
            "batch_name",
            "encrypted_code",
            "code_hash",
            "human_code",
            "license_type",
            "status",
            "user",
            "user_email",
            "generated_by",
            "generated_by_email",
            "max_activations",
            "activation_count",
            "concurrent_limit",
            "device_fingerprint",
            "device_name",
            "device_info",
            "created_at",
            "activated_at",
            "expires_at",
            "last_used_at",
            "revoked_at",
            "revoked_by",
            "revoked_by_email",
            "revoked_reason",
            "notes",
            "custom_data",
            "is_valid",
            "is_expired",
            "is_revoked",
            "remaining_activations",
            "days_until_expiry",
            "license_file",
        ]
        read_only_fields = [
            "id",
            "encrypted_code",
            "code_hash",
            "created_at",
            "activated_at",
            "revoked_at",
            "last_used_at",
            "is_valid",
            "is_expired",
            "is_revoked",
            "remaining_activations",
            "days_until_expiry",
        ]
        extra_kwargs = {
            "human_code": {"required": False},  # Generated automatically
            "encrypted_code": {"write_only": True},
            "code_hash": {"write_only": True},
        }

    def get_license_file(self, obj):
        """
        Generate an encrypted license file (v1.1) with hardware binding and expiry.
        Requires `hardware_id` in serializer context.
        """
        request = self.context.get("request")
        hardware_id = self.context.get("hardware_id")

        # Only generate if explicitly requested (via context) and user is authorized
        if not hardware_id or not request or not request.user.is_authenticated:
            return None

        # Only owner or admin can retrieve license file
        if obj.user != request.user and request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            return None

        from .utils.encryption import LicenseEncryptionManager

        # Prepare claims (the data that will be encrypted inside the license)
        claims = {
            "activation_id": str(obj.id),
            "human_code": obj.human_code,
            "license_type": obj.license_type,
            "software": {
                "id": str(obj.software.id),
                "name": obj.software.name,
                "app_code": obj.software.app_code,
            },
            "user": {
                "id": str(obj.user.id) if obj.user else None,
                "email": obj.user.email if obj.user else None,
            },
            "features": [],  # Populated from LicenseFeature if needed
        }

        # Determine expiry days (use batch setting or default)
        expiry_days = (
            obj.batch.expires_in_days
            if obj.batch
            else getattr(settings, "LICENSE_KEY_SETTINGS", {}).get("DEFAULT_EXPIRY_DAYS", 365)
        )

        manager = LicenseEncryptionManager()
        encrypted_package = manager.create_license_file_with_binding(
            license_data=claims,
            hardware_id=hardware_id,
            expiry_days=expiry_days,
        )
        return encrypted_package.decode()

    def validate_human_code(self, value):
        """Validate activation code format."""
        from .utils.key_generation import ActivationKeyGenerator

        clean_code = value.strip().replace(" ", "").upper()
        validation = ActivationKeyGenerator.validate_key_format(
            key=clean_code,
            expected_format="STANDARD",
            expected_length=25,
        )
        if not validation["valid"]:
            raise serializers.ValidationError(validation["error"])
        return clean_code

    def validate(self, attrs):
        """Ensure code uniqueness and valid expiry."""
        if self.instance is None:  # Creating a new code manually
            software = attrs.get("software")
            human_code = attrs.get("human_code")
            if software and human_code:
                code_hash = hashlib.sha256(human_code.encode()).hexdigest()
                if ActivationCode.objects.filter(code_hash=code_hash).exists():
                    raise serializers.ValidationError(
                        {"human_code": "Activation code already exists."}
                    )

        expires_at = attrs.get("expires_at")
        if expires_at and expires_at < timezone.now():
            raise serializers.ValidationError(
                {"expires_at": "Expiry date cannot be in the past."}
            )

        max_activations = attrs.get("max_activations", 1)
        if max_activations < 1:
            raise serializers.ValidationError(
                {"max_activations": "Maximum activations must be at least 1."}
            )

        return attrs


# ----------------------------------------------------------------------
# License Feature Serializer (Preserves existing boolean fields)
# ----------------------------------------------------------------------
class LicenseFeatureSerializer(serializers.ModelSerializer):
    software_name = serializers.CharField(source="software.name", read_only=True)

    class Meta:
        model = LicenseFeature
        fields = [
            "id",
            "software",
            "software_name",
            "name",
            "code",
            "description",
            "available_in_trial",
            "available_in_standard",
            "available_in_premium",
            "available_in_enterprise",
            "requires_activation",
            "max_usage",
            "is_active",
            "display_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ----------------------------------------------------------------------
# Code Batch Serializer
# ----------------------------------------------------------------------
class CodeBatchSerializer(serializers.ModelSerializer):
    software_name = serializers.CharField(source="software.name", read_only=True)
    generated_by_email = serializers.EmailField(source="generated_by.email", read_only=True)
    unused_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CodeBatch
        fields = [
            "id",
            "software",
            "software_name",
            "name",
            "description",
            "license_type",
            "count",
            "max_activations",
            "expires_in_days",
            "prefix",
            "is_used",
            "used_count",
            "unused_count",
            "generated_by",
            "generated_by_email",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "unused_count"]


# ----------------------------------------------------------------------
# Activation Log Serializer
# ----------------------------------------------------------------------
class ActivationLogSerializer(serializers.ModelSerializer):
    activation_code_human = serializers.CharField(
        source="activation_code.human_code", read_only=True
    )
    software_name = serializers.CharField(
        source="activation_code.software.name", read_only=True
    )

    class Meta:
        model = ActivationLog
        fields = [
            "id",
            "activation_code",
            "activation_code_human",
            "software_name",
            "device_fingerprint",
            "device_name",
            "device_info",
            "ip_address",
            "user_agent",
            "location",
            "action",
            "success",
            "error_message",
            "is_suspicious",
            "suspicion_reason",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ----------------------------------------------------------------------
# License Usage Serializer
# ----------------------------------------------------------------------
class LicenseUsageSerializer(serializers.ModelSerializer):
    activation_code_human = serializers.CharField(
        source="activation_code.human_code", read_only=True
    )
    feature_name = serializers.CharField(source="feature.name", read_only=True)
    feature_code = serializers.CharField(source="feature.code", read_only=True)

    class Meta:
        model = LicenseUsage
        fields = [
            "id",
            "activation_code",
            "activation_code_human",
            "feature",
            "feature_name",
            "feature_code",
            "usage_count",
            "usage_data",
            "device_fingerprint",
            "ip_address",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ----------------------------------------------------------------------
# Revocation Log Serializer
# ----------------------------------------------------------------------
class RevocationLogSerializer(serializers.ModelSerializer):
    activation_code_human = serializers.CharField(
        source="activation_code.human_code", read_only=True
    )
    revoked_by_email = serializers.EmailField(
        source="revoked_by.email", read_only=True, allow_null=True
    )
    undone_by_email = serializers.EmailField(
        source="undone_by.email", read_only=True, allow_null=True
    )

    class Meta:
        model = RevocationLog
        fields = [
            "id",
            "activation_code",
            "activation_code_human",
            "revoked_by",
            "revoked_by_email",
            "reason",
            "details",
            "undone",
            "undone_by",
            "undone_by_email",
            "undone_at",
            "undo_reason",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ----------------------------------------------------------------------
# Activation Request Serializer
# ----------------------------------------------------------------------
class ActivationRequestSerializer(serializers.Serializer):
    activation_code = serializers.CharField(required=True, max_length=50)
    software_slug = serializers.SlugField(required=True)
    device_fingerprint = serializers.CharField(required=False, allow_blank=True)
    device_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    device_info = serializers.JSONField(required=False, default=dict)
    force_activation = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        request = self.context.get("request")
        software_slug = attrs["software_slug"]

        try:
            software = Software.objects.get(slug=software_slug, is_active=True)
        except Software.DoesNotExist:
            raise serializers.ValidationError(
                {"software_slug": f'Software "{software_slug}" not found or inactive.'}
            )
        attrs["software"] = software

        clean_code = attrs["activation_code"].strip().replace(" ", "").upper()
        attrs["activation_code"] = clean_code

        # Find activation code
        try:
            code = ActivationCode.objects.get(human_code=clean_code, software=software)
        except ActivationCode.DoesNotExist:
            # Try by hash
            code_hash = hashlib.sha256(clean_code.encode()).hexdigest()
            try:
                code = ActivationCode.objects.get(code_hash=code_hash, software=software)
            except ActivationCode.DoesNotExist:
                raise serializers.ValidationError(
                    {"activation_code": "Invalid activation code for this software."}
                )

        attrs["activation_code_obj"] = code

        # Check user assignment
        if request and request.user.is_authenticated:
            if code.user and code.user != request.user:
                raise serializers.ValidationError(
                    {"activation_code": "This activation code is already assigned to another user."}
                )

        return attrs


# ----------------------------------------------------------------------
# Activation Response Serializer (Enhanced V1.1 License File)
# ----------------------------------------------------------------------
class ActivationResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    activation_id = serializers.UUIDField(allow_null=True)
    license_file = serializers.CharField(allow_null=True)  # Base64 JSON blob
    download_url = serializers.URLField(allow_null=True)
    message = serializers.CharField()
    warnings = serializers.ListField(child=serializers.CharField(), required=False)
    requires_verification = serializers.BooleanField(default=False)
    verification_method = serializers.CharField(allow_null=True)
    hardware_id_required = serializers.BooleanField(default=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if hasattr(self, "activation_code") and self.activation_code:
            data["software"] = {
                "name": self.activation_code.software.name,
                "slug": self.activation_code.software.slug,
                "version": (
                    self.activation_code.software_version.version_number
                    if self.activation_code.software_version
                    else None
                ),
            }
        return data


# ----------------------------------------------------------------------
# Validation Serializer (No Activation)
# ----------------------------------------------------------------------
class ValidateActivationSerializer(serializers.Serializer):
    activation_code = serializers.CharField(required=True)
    software_slug = serializers.SlugField(required=True)
    device_fingerprint = serializers.CharField(required=False, allow_blank=True)
    check_only = serializers.BooleanField(default=False)

    def validate(self, attrs):
        # Similar to ActivationRequestSerializer but without assignment checks
        software_slug = attrs["software_slug"]
        try:
            software = Software.objects.get(slug=software_slug, is_active=True)
        except Software.DoesNotExist:
            raise serializers.ValidationError(
                {"software_slug": f'Software "{software_slug}" not found or inactive.'}
            )
        attrs["software"] = software

        clean_code = attrs["activation_code"].strip().replace(" ", "").upper()
        attrs["activation_code"] = clean_code

        try:
            code = ActivationCode.objects.get(human_code=clean_code, software=software)
        except ActivationCode.DoesNotExist:
            code_hash = hashlib.sha256(clean_code.encode()).hexdigest()
            try:
                code = ActivationCode.objects.get(code_hash=code_hash, software=software)
            except ActivationCode.DoesNotExist:
                raise serializers.ValidationError(
                    {"activation_code": "Invalid activation code for this software."}
                )

        attrs["activation_code_obj"] = code
        return attrs


# ----------------------------------------------------------------------
# Deactivation Request Serializer
# ----------------------------------------------------------------------
class DeactivationRequestSerializer(serializers.Serializer):
    activation_id = serializers.UUIDField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    keep_license = serializers.BooleanField(default=False)

    def validate(self, attrs):
        request = self.context.get("request")
        try:
            code = ActivationCode.objects.get(id=attrs["activation_id"])
        except ActivationCode.DoesNotExist:
            raise serializers.ValidationError(
                {"activation_id": "Activation code not found."}
            )

        if request and request.user.is_authenticated:
            if code.user != request.user and request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
                raise serializers.ValidationError(
                    {"activation_id": "You do not have permission to deactivate this code."}
                )

        attrs["activation_code"] = code
        return attrs


# ----------------------------------------------------------------------
# Revocation Request Serializer (Admin only)
# ----------------------------------------------------------------------
class RevocationRequestSerializer(serializers.Serializer):
    activation_id = serializers.UUIDField(required=True)
    reason = serializers.CharField(required=True)
    notify_user = serializers.BooleanField(default=True)

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            raise serializers.ValidationError(
                {"detail": "Only administrators can revoke licenses."}
            )

        try:
            code = ActivationCode.objects.get(id=attrs["activation_id"])
        except ActivationCode.DoesNotExist:
            raise serializers.ValidationError(
                {"activation_id": "Activation code not found."}
            )

        attrs["activation_code"] = code
        return attrs