"""
Products models for Software Distribution Platform.
"""
import uuid
import hashlib
import os
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.urls import reverse
from django.conf import settings


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
    
    @property
    def software_count(self):
        return self.software.filter(is_active=True).count()


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
        default=0.00
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
            # Existing indexes (preserved)
            models.Index(fields=["slug"]),
            models.Index(fields=["app_code"]),
            models.Index(fields=["is_active", "is_featured"]),
            models.Index(fields=["category", "is_active"]),
            # New performance indexes (with custom names to avoid conflicts)
            models.Index(fields=["-download_count"], name="software_download_idx"),
            models.Index(fields=["-released_at"], name="software_release_idx"),
            models.Index(fields=["license_type"], name="software_license_idx"),
            models.Index(fields=["base_price"], name="software_price_idx"),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.app_code})"
    
    @property
    def current_version(self):
        """Get current active version."""
        return self.get_latest_version(include_beta=False)
    
    @property
    def price_formatted(self):
        """Get formatted price."""
        return f"{self.currency} {self.base_price:.2f}"
    
    # ---------- Enhanced methods (fully aligned) ----------
    
    def get_latest_version(self, include_beta=False):
        """Get latest version of software."""
        queryset = self.versions.filter(is_active=True)
        if not include_beta:
            queryset = queryset.filter(is_beta=False)
        return queryset.order_by('-version_number').first()
    
    def get_download_url(self, version=None):
        """Get secure download URL for software version (valid 1 hour)."""
        if not version:
            version = self.get_latest_version(include_beta=False)
        if not version:
            return None
        
        # Generate secure token
        token_data = f"{self.id}|{version.id}|{int(timezone.now().timestamp())}"
        token = hashlib.sha256(f"{token_data}{settings.SECRET_KEY}".encode()).hexdigest()[:32]
        
        return reverse('software-version-download', kwargs={
            'slug': self.slug,
            'version_id': version.id,
            'token': token
        })
    
    def increment_download_count(self):
        """Increment download counter atomically."""
        from django.db.models import F
        Software.objects.filter(id=self.id).update(download_count=F('download_count') + 1)
        self.refresh_from_db()
    
    def get_supported_os_list(self):
        """Get list of supported operating systems across all active versions."""
        supported_os = set()
        for version in self.versions.filter(is_active=True):
            if version.supported_os:
                supported_os.update(version.supported_os)
        return list(supported_os)
    
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
            'price': float(self.base_price * 1.5),  # example multiplier
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
    
    # Release info
    release_name = models.CharField(_("release name"), max_length=100, blank=True)
    release_notes = models.TextField(_("release notes"), blank=True)
    changelog = models.TextField(_("changelog"), blank=True)
    
    # Files
    binary_file = models.FileField(
        _("binary file"),
        upload_to="software/%Y/%m/%d/",
        max_length=500
    )
    binary_size = models.BigIntegerField(_("binary size"), default=0)
    binary_checksum = models.CharField(
        _("binary checksum"),
        max_length=64,
        blank=True,
        help_text=_("SHA-256 checksum of the binary")
    )
    installer_file = models.FileField(
        _("installer file"),
        upload_to="installers/%Y/%m/%d/",
        max_length=500,
        blank=True,
        null=True
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
        null=True
    )
    
    # Metadata
    download_count = models.IntegerField(_("download count"), default=0)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    released_at = models.DateTimeField(_("released at"), default=timezone.now)
    
    class Meta:
        verbose_name = _("software version")
        verbose_name_plural = _("software versions")
        ordering = ["-version_number"]
        unique_together = ["software", "version_number"]
        indexes = [
            # Existing indexes
            models.Index(fields=["software", "is_active"]),
            models.Index(fields=["is_active", "is_stable"]),
            models.Index(fields=["released_at"]),
            # New performance indexes (with custom names)
            models.Index(fields=["-download_count"], name="version_download_idx"),
            models.Index(fields=["version_number"], name="version_num_idx"),
            models.Index(fields=["binary_checksum"], name="version_checksum_idx"),
        ]
    
    def __str__(self):
        return f"{self.software.name} v{self.version_number}"
    
    def save(self, *args, **kwargs):
        """Calculate checksum and update file size on save."""
        if self.binary_file and not self.binary_checksum:
            self.binary_checksum = self.calculate_checksum()
        if self.binary_file:
            self.binary_size = self.binary_file.size
        super().save(*args, **kwargs)
    
    def calculate_checksum(self):
        """Calculate SHA-256 checksum of binary file."""
        sha256 = hashlib.sha256()
        self.binary_file.seek(0)
        for chunk in iter(lambda: self.binary_file.read(4096), b""):
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
        max_length=500
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
        max_length=500
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
    
    def __str__(self):
        return f"{self.software.name} - {self.title}"