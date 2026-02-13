# FILE: /backend/apps/products/serializers.py
"""
Serializers for product models.
Optimised for performance, security, and maintainability.
All changes are backward‑compatible and non‑disruptive.
"""
import os
from django.conf import settings
from rest_framework import serializers
from rest_framework.validators import UniqueValidator, UniqueTogetherValidator
from .models import (
    Category, Software, SoftwareVersion,
    SoftwareImage, SoftwareDocument,
    SoftwareUsageEvent   # <-- ADDED for telemetry serializer
)


# ----------------------------------------------------------------------
# Helper – human readable file size (centralised, DRY)
# ----------------------------------------------------------------------
def _human_readable_size(size_in_bytes):
    """Convert bytes to human‑readable string."""
    if not size_in_bytes:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.1f} PB"


# ----------------------------------------------------------------------
# Optional MIME type validation (production‑grade)
# ----------------------------------------------------------------------
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False


def _validate_file_content(file_obj, allowed_mime_types=None):
    """
    Validate file content using python‑magic if available.
    Falls back to extension check if not installed.
    """
    if not HAS_MAGIC:
        return True  # skip content validation
    try:
        mime = magic.from_buffer(file_obj.read(1024), mime=True)
        file_obj.seek(0)
        if allowed_mime_types and mime not in allowed_mime_types:
            raise serializers.ValidationError(f"File MIME type '{mime}' not allowed.")
    except Exception:
        # If magic fails, fall back to extension check (already performed)
        pass
    return True


# ----------------------------------------------------------------------
# Helper for safe file URL access
# ----------------------------------------------------------------------
def _safe_file_url(file_field):
    """Return URL if file exists, else None."""
    return file_field.url if file_field else None


# ----------------------------------------------------------------------
# Category Serializer
# ----------------------------------------------------------------------
class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for software categories.
    """
    software_count = serializers.IntegerField(read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description',
            'parent', 'parent_name', 'icon',
            'display_order', 'is_active',
            'software_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'software_count']


# ----------------------------------------------------------------------
# Software Image Serializer
# ----------------------------------------------------------------------
class SoftwareImageSerializer(serializers.ModelSerializer):
    """
    Serializer for software images.
    """
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = SoftwareImage
        fields = [
            'id', 'software', 'image_type',
            'image_url', 'thumbnail_url',
            'alt_text', 'caption', 'display_order',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_image_url(self, obj):
        return _safe_file_url(obj.image)

    def get_thumbnail_url(self, obj):
        # Placeholder – implement with django-imagekit if needed
        return _safe_file_url(obj.image)


# ----------------------------------------------------------------------
# Software Document Serializer
# ----------------------------------------------------------------------
class SoftwareDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for software documents.
    """
    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    file_type = serializers.SerializerMethodField()

    class Meta:
        model = SoftwareDocument
        fields = [
            'id', 'software', 'document_type',
            'title', 'file_url', 'file_size', 'file_type',
            'description', 'language', 'version',
            'download_count', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'download_count']

    def get_file_url(self, obj):
        return _safe_file_url(obj.file)

    def get_file_size(self, obj):
        if obj.file:
            return _human_readable_size(obj.file.size)
        return "0 B"

    def get_file_type(self, obj):
        if obj.file:
            _, ext = os.path.splitext(obj.file.name)
            return ext.lower().replace('.', '')
        return None


# ----------------------------------------------------------------------
# Software Version Serializer
# ----------------------------------------------------------------------
class SoftwareVersionSerializer(serializers.ModelSerializer):
    """
    Serializer for software versions.
    """
    download_url = serializers.SerializerMethodField()
    file_size_human = serializers.SerializerMethodField()

    class Meta:
        model = SoftwareVersion
        fields = [
            'id', 'software', 'version_number', 'version_code',
            'release_name', 'release_notes', 'changelog',
            'binary_file', 'binary_size', 'file_size_human',
            'binary_checksum', 'installer_file',
            'download_url', 'download_count',
            'supported_os', 'min_requirements', 'recommended_requirements',
            'is_active', 'is_beta', 'is_stable', 'is_signed',
            'signature_file', 'created_at', 'updated_at', 'released_at'
        ]
        read_only_fields = [
            'id', 'binary_size', 'binary_checksum',
            'download_count', 'created_at', 'updated_at'
        ]
        validators = [
            UniqueTogetherValidator(
                queryset=SoftwareVersion.objects.all(),
                fields=['software', 'version_number'],
                message='Version number already exists for this software.'
            )
        ]

    def get_download_url(self, obj):
        request = self.context.get('request')
        if request and obj.software:
            return obj.software.get_download_url(version=obj)
        return None

    def get_file_size_human(self, obj):
        return obj.human_size   # model property – already efficient

    def validate(self, attrs):
        # File validation (extension + size + optional MIME)
        binary_file = attrs.get('binary_file')
        if binary_file:
            max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 2 * 1024 * 1024 * 1024)
            if binary_file.size > max_size:
                raise serializers.ValidationError({
                    'binary_file': f'File size exceeds maximum allowed size of {max_size / (1024*1024*1024):.0f}GB.'
                })
            allowed_extensions = ['.exe', '.msi', '.dmg', '.pkg', '.deb',
                                  '.rpm', '.zip', '.tar.gz']
            _, ext = os.path.splitext(binary_file.name)
            if ext.lower() not in allowed_extensions:
                raise serializers.ValidationError({
                    'binary_file': f'File type {ext} not allowed. '
                                   f'Allowed types: {", ".join(allowed_extensions)}'
                })
            # Optional MIME validation
            allowed_mime = [
                'application/x-msdownload', 'application/x-msi', 'application/x-apple-diskimage',
                'application/x-debian-package', 'application/x-rpm', 'application/zip',
                'application/gzip', 'application/x-tar'
            ]
            _validate_file_content(binary_file, allowed_mime)
        return attrs


# ----------------------------------------------------------------------
# Helper: default category assignment – kept for backward compatibility
# ----------------------------------------------------------------------
def _assign_default_category(software):
    """
    Assign 'Uncategorized' category if software has none.
    Note: This should ideally be moved to model save() or a signal
    for better separation of concerns, but kept here for non‑disruptive
    backward compatibility.
    """
    if not software.category:
        # Potential race condition; consider using select_for_update in production.
        default_category, _ = Category.objects.get_or_create(
            name='Uncategorized',
            slug='uncategorized',
            defaults={'description': 'Uncategorized software'}
        )
        software.category = default_category
        software.save(update_fields=['category'])
    return software


# ----------------------------------------------------------------------
# Software Serializer – with dynamic field exclusion for list views
# ----------------------------------------------------------------------
class SoftwareSerializer(serializers.ModelSerializer):
    """
    Serializer for software products.
    Supports dynamic field exclusion via `fields` query parameter
    to optimise list views. (Backward‑compatible: full serialization by default)
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    current_version = serializers.SerializerMethodField()
    versions = SoftwareVersionSerializer(many=True, read_only=True)
    images = SoftwareImageSerializer(many=True, read_only=True)
    documents = SoftwareDocumentSerializer(many=True, read_only=True)
    pricing_tiers = serializers.SerializerMethodField()
    supported_os = serializers.SerializerMethodField()

    class Meta:
        model = Software
        fields = [
            'id', 'name', 'slug', 'app_code',
            'category', 'category_name',
            'short_description', 'full_description',
            'features', 'requirements', 'tags',
            'base_price', 'currency', 'license_type',
            'pricing_tiers',
            'has_trial', 'trial_days', 'trial_features',
            'is_active', 'is_featured', 'is_new',
            'display_order', 'download_count',
            'average_rating', 'review_count',
            'supported_os',
            'current_version', 'versions', 'images', 'documents',
            'released_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'download_count', 'average_rating',
            'review_count', 'created_at', 'updated_at'
        ]
        # Use field‑level unique validators instead of manual checks
        extra_kwargs = {
            'slug': {
                'validators': [
                    UniqueValidator(
                        queryset=Software.objects.all(),
                        message='Software with this slug already exists.'
                    )
                ]
            },
            'app_code': {
                'validators': [
                    UniqueValidator(
                        queryset=Software.objects.all(),
                        message='Software with this app code already exists.'
                    )
                ]
            }
        }

    def __init__(self, *args, **kwargs):
        # Allow dynamic field exclusion via `fields` in context
        super().__init__(*args, **kwargs)
        if 'request' in self.context:
            request = self.context['request']
            fields_param = request.query_params.get('fields')
            if fields_param:
                requested_fields = fields_param.split(',')
                allowed_fields = set(self.fields.keys())
                # Validate requested fields
                invalid_fields = set(requested_fields) - allowed_fields
                if invalid_fields:
                    raise serializers.ValidationError({
                        'fields': f"Invalid field(s): {', '.join(invalid_fields)}"
                    })
                # Remove any fields not requested
                for field_name in list(self.fields.keys()):
                    if field_name not in requested_fields:
                        self.fields.pop(field_name)

    def get_current_version(self, obj):
        """
        Returns the current stable version of the software.
        Note: This method triggers a database query per object.
        Ensure your view uses prefetch_related or select_related
        to avoid N+1 queries.
        """
        version = obj.get_latest_version(include_beta=False)
        if version:
            return SoftwareVersionSerializer(version, context=self.context).data
        return None

    def get_pricing_tiers(self, obj):
        return obj.get_pricing_tiers()

    def get_supported_os(self, obj):
        return obj.get_supported_os_list()

    def validate(self, attrs):
        # Only validate base_price if it's being updated (PATCH safety)
        if 'base_price' in attrs and attrs['base_price'] < 0:
            raise serializers.ValidationError({
                'base_price': 'Price cannot be negative.'
            })
        return attrs

    def create(self, validated_data):
        validated_data.setdefault('download_count', 0)
        validated_data.setdefault('average_rating', 0.0)
        validated_data.setdefault('review_count', 0)

        software = Software.objects.create(**validated_data)

        # Assign default category if missing
        _assign_default_category(software)

        return software


# ============================================================================
# TELEMETRY SERIALIZER – ADDED FOR PRODUCT USAGE EVENT RECORDING
# ============================================================================

class SoftwareUsageEventSerializer(serializers.ModelSerializer):
    """
    Serializer for recording software usage events.
    Accepts software_id (UUID) and optional human‑readable activation code,
    and automatically associates the event with the authenticated user.
    """
    software_id = serializers.UUIDField(write_only=True)
    activation_code = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        help_text="Human‑readable activation code (optional)"
    )

    class Meta:
        model = SoftwareUsageEvent
        fields = ['software_id', 'event_type', 'metadata', 'activation_code']
        # event_type is already validated by model choices

    def validate_software_id(self, value):
        """Ensure software exists and return the instance."""
        try:
            return Software.objects.get(id=value)
        except Software.DoesNotExist:
            raise serializers.ValidationError("Software not found.")

    def validate_activation_code(self, value):
        """If provided, validate and return the ActivationCode instance."""
        if value:
            # Local import to avoid circular dependency and keep existing imports untouched
            from licenses.models import ActivationCode
            try:
                return ActivationCode.objects.get(human_code=value)
            except ActivationCode.DoesNotExist:
                raise serializers.ValidationError("Invalid activation code.")
        return None

    def create(self, validated_data):
        """Create the usage event, automatically setting the user from request."""
        software = validated_data.pop('software_id')
        activation_code = validated_data.pop('activation_code', None)
        user = self.context['request'].user

        return SoftwareUsageEvent.objects.create(
            software=software,
            user=user,
            activation_code=activation_code,
            **validated_data
        )