# FILE: /backend/apps/products/models.py
"""
Products models for Software Distribution Platform.
Enhanced with semantic versioning, secure download tokens, file validation,
and improved performance.
All changes are backward‑compatible and non‑disruptive.
"""
import uuid
import hashlib
import os
from decimal import Decimal

from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.core.exceptions import ValidationError

# Optional semantic versioning library – gracefully degrades if not installed
try:
    from packaging.version import parse as parse_version
except ImportError:
    parse_version = None


def parse_version_number(version_str):
    """
    Parse a version string into (major, minor, patch, prerelease).
    Returns a tuple of integers (major, minor, patch) and a string for prerelease.
    """
    if parse_version is not None:
        try:
            v = parse_version(version_str)
            # Extract major, minor, micro (patch)
            major = v.major if v.major is not None else 0
            minor = v.minor if v.minor is not None else 0
            patch = v.micro if v.micro is not None else 0
            return major, minor, patch, str(v.pre) if v.pre else ''
        except Exception:
            pass
    # Fallback: simple integer extraction
    parts = version_str.replace('-', '.').replace('_', '.').split('.')
    major = int(parts[0]) if parts and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return major, minor, patch, ''


class Category(models.Model):
    """Software category for organization."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=100, unique=True)
    slug = models.SlugField(_("slug"), max_length=100, unique=True)
    description = models.TextField(_("description"), blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategories"
    )
    icon = models.CharField(_("icon"), max_length=50, blank=True, help_text=_("FontAwesome icon class"))
    
    # Metadata
    display_order = models.IntegerField(_("display order"), default=0)
    is_active = models.BooleanField(_("active"), default=True)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    
    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")
        ordering = ["display_order", "name"]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Prevent circular parent relationships."""
        if self.parent and self.parent.pk == self.pk:
            raise ValidationError({'parent': _("A category cannot be its own parent.")})
        # Check deeper cycles (grandparent, etc.)
        if self.parent:
            ancestor = self.parent
            while ancestor:
                if ancestor.pk == self.pk:
                    raise ValidationError({'parent': _("Circular parent relationship detected.")})
                ancestor = ancestor.parent
    
    @property
    def software_count(self):
        """Return count of active software in this category."""
        # Use cached annotation when available (see admin.py)
        return getattr(self, '_software_count', self.software.filter(is_active=True).count())


class Software(models.Model):
    """Software product model."""
    
    LICENSE_TYPES = [
        ("PERPETUAL", "Perpetual"),
        ("SUBSCRIPTION", "Subscription"),
        ("TRIAL", "Trial"),
        ("FLOATING", "Floating"),
        ("CONCURRENT", "Concurrent"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=255, unique=True)
    app_code = models.CharField(
        _("application code"),
        max_length=10,
        unique=True,
        help_text=_("Unique code for this software (e.g., 'WINAPP001')")
    )
    
    # Categorization
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="software"
    )
    tags = models.JSONField(
        _("tags"),
        default=list,
        help_text=_("List of tags for filtering")
    )
    
    # Description
    short_description = models.TextField(_("short description"), blank=True)
    full_description = models.TextField(_("full description"), blank=True)
    features = models.JSONField(
        _("features"),
        default=list,
        help_text=_("List of features")
    )
    requirements = models.JSONField(
        _("requirements"),
        default=list,
        help_text=_("System requirements")
    )
    
    # Pricing
    base_price = models.DecimalField(
        _("base price"),
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    currency = models.CharField(_("currency"), max_length=3, default="USD")
    license_type = models.CharField(
        _("license type"),
        max_length=20,
        choices=LICENSE_TYPES,
        default="PERPETUAL"
    )
    
    # Trial settings
    has_trial = models.BooleanField(_("has trial"), default=False)
    trial_days = models.IntegerField(_("trial days"), default=14)
    trial_features = models.JSONField(
        _("trial features"),
        default=list,
        help_text=_("Features available in trial version")
    )
    
    # Status
    is_active = models.BooleanField(_("active"), default=True)
    is_featured = models.BooleanField(_("featured"), default=False)
    is_new = models.BooleanField(_("new"), default=False)
    
    # Metadata
    display_order = models.IntegerField(_("display order"), default=0)
    download_count = models.IntegerField(_("download count"), default=0)
    average_rating = models.FloatField(_("average rating"), default=0.0)
    review_count = models.IntegerField(_("review count"), default=0)
    
    # Timestamps
    released_at = models.DateTimeField(_("released at"), default=timezone.now)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    
    class Meta:
        verbose_name = _("software")
        verbose_name_plural = _("software")
        ordering = ["display_order", "name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["app_code"]),
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["-download_count"], name="software_download_idx"),
            models.Index(fields=["-released_at"], name="software_release_idx"),
            models.Index(fields=["license_type"], name="software_license_idx"),
            models.Index(fields=["base_price"], name="software_price_idx"),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.app_code})"
    
    @property
    def current_version(self):
        """Get current active version (stable)."""
        return self.get_latest_version(include_beta=False)
    
    @property
    def price_formatted(self):
        """Get formatted price (i18n‑aware fallback)."""
        try:
            import locale
            locale.setlocale(locale.LC_ALL, '')
            return locale.currency(float(self.base_price), grouping=True)
        except (ImportError, locale.Error):
            return f"{self.currency} {self.base_price:.2f}"
    
    # ---------- Enhanced methods (fully backward‑compatible) ----------
    
    def get_latest_version(self, include_beta=False):
        """
        Get the latest version using semantic ordering.
        Falls back to string ordering if packaging not installed.
        """
        queryset = self.versions.filter(is_active=True)
        if not include_beta:
            queryset = queryset.filter(is_beta=False)
        
        versions = list(queryset)
        if not versions:
            return None
        
        # Use semantic version comparison if available
        if parse_version is not None:
            versions.sort(
                key=lambda v: parse_version(v.version_number),
                reverse=True
            )
        else:
            # Fallback to string order (still better than none)
            versions.sort(key=lambda v: v.version_number, reverse=True)
        return versions[0]
    
    def get_download_url(self, version=None, expiry_seconds=3600):
        """
        Generate a secure, time‑limited download URL using Django's signing framework.
        Token is signed and includes an expiration timestamp.
        """
        from django.core.signing import TimestampSigner, dumps
        from django.urls import reverse
        
        if not version:
            version = self.get_latest_version(include_beta=False)
        if not version:
            return None
        
        # Create a signed payload with timestamp (expiry handled by signer)
        signer = TimestampSigner()
        payload = {
            'software_id': str(self.id),
            'version_id': str(version.id),
            'user_id': 'anonymous'  # Can be replaced with actual user ID if authenticated
        }
        signed_token = signer.sign(dumps(payload))
        
        return reverse('software-version-download', kwargs={
            'slug': self.slug,
            'version_id': version.id,
            'token': signed_token
        })
    
    def increment_download_count(self):
        """Increment download counter atomically."""
        from django.db.models import F
        Software.objects.filter(id=self.id).update(download_count=F('download_count') + 1)
        self.refresh_from_db()
    
    def get_supported_os_list(self):
        """Get list of supported operating systems across all active versions."""
        # Use a single query with values_list and distinct for efficiency
        os_entries = self.versions.filter(
            is_active=True
        ).exclude(
            supported_os__exact=[]
        ).values_list('supported_os', flat=True)
        
        supported = set()
        for entry in os_entries:
            if isinstance(entry, list):
                supported.update(entry)
        return list(supported)
    
    def get_pricing_tiers(self):
        """
        Get available pricing tiers based on license type.
        Returns a dictionary compatible with frontend pricing display.
        """
        tiers = {
            'trial': {
                'available': self.has_trial,
                'days': self.trial_days,
                'price': 0.00,
                'features': self.trial_features or []
            },
            'standard': {
                'available': True,
                'price': float(self.base_price),
                'features': self.features or []
            }
        }
        
        # Define "premium" tier for non‑trial, paid license types
        is_paid = self.license_type not in ['TRIAL'] and self.base_price > 0
        tiers['premium'] = {
            'available': is_paid,
            'price': float(self.base_price * Decimal('1.5')),
            'features': (self.features or []) + [
                'Priority Support',
                'Advanced Features',
                'Custom Integration'
            ]
        }
        return tiers


class SoftwareVersion(models.Model):
    """Specific version of software."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    software = models.ForeignKey(
        Software,
        on_delete=models.CASCADE,
        related_name="versions"
    )
    version_number = models.CharField(_("version number"), max_length=50)
    version_code = models.CharField(
        _("version code"),
        max_length=20,
        help_text=_("Internal version code (e.g., '1.0.0.1234')")
    )
    
    # ----- NEW: Semantic version components (non‑disruptive) -----
    version_major = models.IntegerField(
        _("major version"),
        null=True,
        blank=True,
        editable=False,
        help_text=_("Auto‑populated from version_number")
    )
    version_minor = models.IntegerField(
        _("minor version"),
        null=True,
        blank=True,
        editable=False
    )
    version_patch = models.IntegerField(
        _("patch version"),
        null=True,
        blank=True,
        editable=False
    )
    version_prerelease = models.CharField(
        _("prerelease tag"),
        max_length=50,
        blank=True,
        editable=False
    )
    # ------------------------------------------------------------
    
    # Release info
    release_name = models.CharField(_("release name"), max_length=100, blank=True)
    release_notes = models.TextField(_("release notes"), blank=True)
    changelog = models.TextField(_("changelog"), blank=True)
    
    # Files with validators
    def validate_file_size(value):
        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 2 * 1024 * 1024 * 1024)  # 2GB default
        if value.size > max_size:
            raise ValidationError(f"File size cannot exceed {max_size / (1024*1024*1024):.0f}GB.")
    
    binary_file = models.FileField(
        _("binary file"),
        upload_to="software/%Y/%m/%d/",
        max_length=500,
        validators=[
            FileExtensionValidator(allowed_extensions=['exe', 'msi', 'dmg', 'deb', 'rpm', 'zip', 'tar.gz', 'appimage']),
            validate_file_size
        ]
    )
    binary_size = models.BigIntegerField(_("binary size"), default=0, editable=False)
    binary_checksum = models.CharField(
        _("binary checksum"),
        max_length=64,
        blank=True,
        editable=False,
        help_text=_("SHA-256 checksum of the binary")
    )
    installer_file = models.FileField(
        _("installer file"),
        upload_to="installers/%Y/%m/%d/",
        max_length=500,
        blank=True,
        null=True,
        validators=[validate_file_size]
    )
    
    # Compatibility
    supported_os = models.JSONField(
        _("supported OS"),
        default=list,
        help_text=_("List of supported operating systems")
    )
    min_requirements = models.JSONField(
        _("minimum requirements"),
        default=dict,
        help_text=_("Minimum system requirements")
    )
    recommended_requirements = models.JSONField(
        _("recommended requirements"),
        default=dict,
        help_text=_("Recommended system requirements")
    )
    
    # Status
    is_active = models.BooleanField(_("active"), default=True)
    is_beta = models.BooleanField(_("beta"), default=False)
    is_stable = models.BooleanField(_("stable"), default=True)
    
    # Security
    is_signed = models.BooleanField(_("signed"), default=False)
    signature_file = models.FileField(
        _("signature file"),
        upload_to="signatures/%Y/%m/%d/",
        max_length=500,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['sig', 'asc', 'sign'])]
    )
    
    # Metadata
    download_count = models.IntegerField(_("download count"), default=0)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    released_at = models.DateTimeField(_("released at"), default=timezone.now)
    
    class Meta:
        verbose_name = _("software version")
        verbose_name_plural = _("software versions")
        ordering = ["software", "-version_major", "-version_minor", "-version_patch", "-version_prerelease"]
        unique_together = ["software", "version_number"]
        indexes = [
            models.Index(fields=["software", "is_active"]),
            models.Index(fields=["is_active", "is_stable"]),
            models.Index(fields=["released_at"]),
            models.Index(fields=["-download_count"], name="version_download_idx"),
            models.Index(fields=["version_major", "version_minor", "version_patch"], name="version_semver_idx"),
            models.Index(fields=["binary_checksum"], name="version_checksum_idx"),
        ]
    
    def __str__(self):
        return f"{self.software.name} v{self.version_number}"
    
    def save(self, *args, **kwargs):
        """
        Calculate checksum, update file size, and parse semantic version.
        Runs within a transaction to ensure consistency.
        """
        with transaction.atomic():
            # Parse version_number into components
            if self.version_number:
                major, minor, patch, pre = parse_version_number(self.version_number)
                self.version_major = major
                self.version_minor = minor
                self.version_patch = patch
                self.version_prerelease = pre[:50] if pre else ''
            
            # Compute checksum and size if a new file is uploaded
            if self.binary_file and not self.binary_checksum:
                # Compute SHA‑256 in chunks (already done, but ensure it's fresh)
                self.binary_checksum = self.calculate_checksum()
            if self.binary_file and self.binary_size != self.binary_file.size:
                self.binary_size = self.binary_file.size
            
            super().save(*args, **kwargs)
    
    def calculate_checksum(self):
        """Calculate SHA-256 checksum of binary file using streaming (memory‑efficient)."""
        sha256 = hashlib.sha256()
        self.binary_file.seek(0)
        for chunk in iter(lambda: self.binary_file.read(65536), b""):
            sha256.update(chunk)
        self.binary_file.seek(0)
        return sha256.hexdigest()
    
    @property
    def filename(self):
        """Get filename without path."""
        return os.path.basename(self.binary_file.name)
    
    @property
    def human_size(self):
        """Get human-readable file size."""
        size = self.binary_size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"


class SoftwareImage(models.Model):
    """Images for software (screenshots, logos, etc.)."""
    
    IMAGE_TYPES = [
        ("LOGO", "Logo"),
        ("SCREENSHOT", "Screenshot"),
        ("BANNER", "Banner"),
        ("ICON", "Icon"),
        ("OTHER", "Other"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    software = models.ForeignKey(
        Software,
        on_delete=models.CASCADE,
        related_name="images"
    )
    image_type = models.CharField(_("image type"), max_length=20, choices=IMAGE_TYPES)
    image = models.ImageField(
        _("image"),
        upload_to="software_images/%Y/%m/%d/",
        max_length=500,
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp']),
        ]
    )
    alt_text = models.CharField(_("alt text"), max_length=255, blank=True)
    caption = models.CharField(_("caption"), max_length=255, blank=True)
    display_order = models.IntegerField(_("display order"), default=0)
    is_active = models.BooleanField(_("active"), default=True)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("software image")
        verbose_name_plural = _("software images")
        ordering = ["display_order"]
        # Enforce at most one logo per software
        constraints = [
            models.UniqueConstraint(
                fields=['software', 'image_type'],
                condition=models.Q(image_type='LOGO'),
                name='unique_logo_per_software'
            )
        ]
    
    def __str__(self):
        return f"{self.software.name} - {self.get_image_type_display()}"


class SoftwareDocument(models.Model):
    """Documents for software (manuals, guides, etc.)."""
    
    DOCUMENT_TYPES = [
        ("MANUAL", "User Manual"),
        ("GUIDE", "Installation Guide"),
        ("API", "API Documentation"),
        ("LICENSE", "License Agreement"),
        ("RELEASE_NOTES", "Release Notes"),
        ("OTHER", "Other"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    software = models.ForeignKey(
        Software,
        on_delete=models.CASCADE,
        related_name="documents"
    )
    document_type = models.CharField(_("document type"), max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(_("title"), max_length=255)
    file = models.FileField(
        _("file"),
        upload_to="software_docs/%Y/%m/%d/",
        max_length=500,
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'txt', 'md', 'rtf']),
        ]
    )
    description = models.TextField(_("description"), blank=True)
    language = models.CharField(_("language"), max_length=10, default="en")
    version = models.CharField(_("version"), max_length=50, blank=True)
    
    download_count = models.IntegerField(_("download count"), default=0)
    is_active = models.BooleanField(_("active"), default=True)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    
    class Meta:
        verbose_name = _("software document")
        verbose_name_plural = _("software documents")
        # Prevent duplicate documents for the same software, type, version, language
        constraints = [
            models.UniqueConstraint(
                fields=['software', 'document_type', 'version', 'language'],
                name='unique_document_per_software_type_version_lang'
            )
        ]
    
    def __str__(self):
        return f"{self.software.name} - {self.title}"


# ============================================================================
# TELEMETRY MODEL – ADDED FOR PRODUCT USAGE ANALYTICS (non‑disruptive)
# ============================================================================

class SoftwareUsageEvent(models.Model):
    """
    Tracks usage events for software (e.g., launch, feature use).
    This is separate from LicenseUsage (which tracks feature limits) for telemetry/analytics.
    """

    class EventTypes(models.TextChoices):
        LAUNCH = "launch", _("Launch")
        FEATURE_X_USED = "feature_x_used", _("Feature X Used")
        # Add more as needed

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    software = models.ForeignKey(
        'Software',
        on_delete=models.CASCADE,
        related_name='usage_events'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='software_usage_events'
    )
    activation_code = models.ForeignKey(
        'licenses.ActivationCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usage_events'
    )
    event_type = models.CharField(
        max_length=50,
        choices=EventTypes.choices,
        help_text=_("Type of usage event")
    )
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("software usage event")
        verbose_name_plural = _("software usage events")
        indexes = [
            models.Index(fields=['software', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['event_type']),
            # Optional composite index for common analytics queries
            models.Index(fields=['software', 'event_type', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        # Anonymized: use user ID instead of email to avoid PII exposure in logs
        return f"{self.event_type} – {self.software.name} – {self.user_id}"