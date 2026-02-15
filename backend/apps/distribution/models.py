# FILE: backend/apps/distribution/models.py
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class Mirror(models.Model):
    """
    Represents a mirror server for software distribution.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    # Normalize base_url: ensure no trailing slash, HTTPS only
    base_url = models.URLField(
        help_text=_("Base URL of the mirror, e.g., https://mirror1.example.com")
    )
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(
        default=100,
        help_text=_("Lower number = higher priority")
    )
    region = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Geographic region, e.g., 'EU'")
    )

    # ----- NEW: health and operational fields (non‑disruptive) -----
    is_online = models.BooleanField(
        default=True,
        help_text=_("Whether the mirror is currently reachable")
    )
    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Last time mirror responded to a health check")
    )
    average_latency_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Average latency in milliseconds")
    )
    failure_count = models.PositiveIntegerField(
        default=0,
        help_text=_("Number of consecutive failed health checks")
    )
    # --------------------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("mirror")
        verbose_name_plural = _("mirrors")
        ordering = ['priority']
        indexes = [
            models.Index(fields=['is_active', 'is_online']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Normalize base_url: strip trailing slash
        if self.base_url and self.base_url.endswith('/'):
            self.base_url = self.base_url.rstrip('/')
        # Enforce HTTPS in production (can be overridden by setting)
        if not settings.DEBUG and self.base_url.startswith('http://'):
            self.base_url = self.base_url.replace('http://', 'https://')
        super().save(*args, **kwargs)


class CDNFile(models.Model):
    """
    Tracks a software file that is distributed via CDN/mirrors.
    The actual file is stored in the associated SoftwareVersion.
    """
    ARTIFACT_TYPES = [
        ('installer', 'Installer'),
        ('binary', 'Binary'),
        ('archive', 'Archive'),
        ('document', 'Documentation'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    software_version = models.ForeignKey(
        'products.SoftwareVersion',
        on_delete=models.PROTECT,           # Changed from CASCADE to preserve historical records
        related_name='cdn_files'
    )
    # ----- NEW: artifact type to distinguish multiple files per version -----
    artifact_type = models.CharField(
        max_length=20,
        choices=ARTIFACT_TYPES,
        default='installer',
        help_text=_("Type of artifact (e.g., installer, binary)")
    )
    # ------------------------------------------------------------------------
    filename = models.CharField(max_length=255)
    file_hash = models.CharField(
        max_length=64,
        blank=False,                         # Changed: now required (no blank)
        help_text=_("SHA-256 of file (mandatory for integrity)")
    )
    file_size = models.PositiveIntegerField(
        null=True,                            # Changed from default=0 to allow null (unknown)
        blank=True,
        help_text=_("File size in bytes")
    )
    mirrors = models.ManyToManyField(
        Mirror,
        through='MirrorFileStatus'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("CDN file")
        verbose_name_plural = _("CDN files")
        # Ensure at most one file per software version (or per version+type)
        constraints = [
            models.UniqueConstraint(
                fields=['software_version', 'artifact_type'],
                name='unique_cdnfile_per_version_type'
            )
        ]
        indexes = [
            models.Index(fields=['software_version']),
            models.Index(fields=['file_hash']),
        ]

    def __str__(self):
        return f"{self.filename} ({self.get_artifact_type_display()})"


class MirrorFileStatus(models.Model):
    """
    Tracks the status of a file on a particular mirror.
    """
    mirror = models.ForeignKey(Mirror, on_delete=models.CASCADE)
    cdn_file = models.ForeignKey(CDNFile, on_delete=models.CASCADE)
    is_synced = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        unique_together = ('mirror', 'cdn_file')
        indexes = [
            models.Index(fields=['cdn_file', 'is_synced']),  # ← Critical for performance
        ]
        verbose_name = _("mirror file status")
        verbose_name_plural = _("mirror file statuses")

    def __str__(self):
        return f"{self.cdn_file.filename} on {self.mirror.name}"

    @property
    def url(self):
        """Generate the full download URL dynamically."""
        return f"{self.mirror.base_url.rstrip('/')}/{self.cdn_file.filename.lstrip('/')}"