"""
Licenses models for Software Distribution Platform.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
import secrets
import string
import hashlib

class ActivationCode(models.Model):
    """Activation code/license key model."""
    
    STATUS_CHOICES = [
        ("GENERATED", "Generated"),
        ("ACTIVATED", "Activated"),
        ("REVOKED", "Revoked"),
        ("EXPIRED", "Expired"),
        ("SUSPENDED", "Suspended"),
    ]
    
    TYPE_CHOICES = [
        ("TRIAL", "Trial"),
        ("STANDARD", "Standard"),
        ("PREMIUM", "Premium"),
        ("ENTERPRISE", "Enterprise"),
        ("LIFETIME", "Lifetime"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Software relationship
    software = models.ForeignKey(
        "products.Software",
        on_delete=models.CASCADE,
        related_name="activation_codes"
    )
    software_version = models.ForeignKey(
        "products.SoftwareVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activation_codes"
    )
    
    # Code data (encrypted)
    encrypted_code = models.BinaryField(_("encrypted code"))
    code_hash = models.CharField(
        _("code hash"),
        max_length=64,
        db_index=True,
        unique=True
    )
    human_code = models.CharField(
        _("human readable code"),
        max_length=50,
        db_index=True,
        help_text=_("Formatted code for users (e.g., ABCD-EFGH-IJKL-MNOP)")
    )
    
    # License properties
    license_type = models.CharField(
        _("license type"),
        max_length=20,
        choices=TYPE_CHOICES,
        default="STANDARD"
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="GENERATED"
    )
    
    # Ownership
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activation_codes"
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="generated_codes"
    )
    
    # Activation limits
    max_activations = models.IntegerField(
        _("max activations"),
        default=1,
        help_text=_("Maximum number of devices that can activate this code")
    )
    activation_count = models.IntegerField(_("activation count"), default=0)
    concurrent_limit = models.IntegerField(
        _("concurrent limit"),
        default=1,
        help_text=_("Maximum concurrent activations")
    )
    
    # Device locking
    device_fingerprint = models.CharField(
        _("device fingerprint"),
        max_length=64,
        blank=True,
        null=True,
        db_index=True
    )
    device_name = models.CharField(_("device name"), max_length=255, blank=True)
    device_info = models.JSONField(
        _("device info"),
        default=dict,
        help_text=_("Additional device information")
    )
    
    # Timestamps
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    activated_at = models.DateTimeField(_("activated at"), null=True, blank=True)
    expires_at = models.DateTimeField(_("expires at"), db_index=True)
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)
    last_used_at = models.DateTimeField(_("last used at"), null=True, blank=True)
    
    # Revocation info
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_codes"
    )
    revoked_reason = models.TextField(_("revoked reason"), blank=True)
    
    # Metadata
    notes = models.TextField(_("notes"), blank=True)
    custom_data = models.JSONField(
        _("custom data"),
        default=dict,
        help_text=_("Additional custom data")
    )
    
    class Meta:
        verbose_name = _("activation code")
        verbose_name_plural = _("activation codes")
        indexes = [
            models.Index(fields=["code_hash"]),
            models.Index(fields=["human_code"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["software", "status"]),
            models.Index(fields=["expires_at", "status"]),
            models.Index(fields=["device_fingerprint"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.human_code} - {self.software.name}"
    
    @property
    def is_valid(self):
        """Check if code is valid for activation."""
        now = timezone.now()
        return (
            self.status == "ACTIVATED" and
            not self.is_expired and
            self.activation_count < self.max_activations and
            not self.is_revoked
        )
    
    @property
    def is_expired(self):
        """Check if code is expired."""
        return timezone.now() > self.expires_at
    
    @property
    def is_revoked(self):
        """Check if code is revoked."""
        return self.status == "REVOKED"
    
    @property
    def remaining_activations(self):
        """Get remaining activations."""
        return max(0, self.max_activations - self.activation_count)
    
    @property
    def days_until_expiry(self):
        """Get days until expiry."""
        if not self.expires_at:
            return None
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)
    
    def activate(self, device_fingerprint, device_name="", device_info=None):
        """Activate this code on a device."""
        if not self.is_valid:
            return False
        
        self.status = "ACTIVATED"
        self.device_fingerprint = device_fingerprint
        self.device_name = device_name
        if device_info:
            self.device_info = device_info
        
        if not self.activated_at:
            self.activated_at = timezone.now()
        
        self.activation_count += 1
        self.last_used_at = timezone.now()
        self.save()
        
        # Log activation
        ActivationLog.objects.create(
            activation_code=self,
            device_fingerprint=device_fingerprint,
            action="ACTIVATE",
            success=True
        )
        
        return True
    
    def revoke(self, revoked_by, reason=""):
        """Revoke this activation code."""
        self.status = "REVOKED"
        self.revoked_at = timezone.now()
        self.revoked_by = revoked_by
        self.revoked_reason = reason
        self.save()
        
        # Log revocation
        RevocationLog.objects.create(
            activation_code=self,
            revoked_by=revoked_by,
            reason=reason
        )
        
        return True

class ActivationLog(models.Model):
    """Log of activation attempts."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activation_code = models.ForeignKey(
        ActivationCode,
        on_delete=models.CASCADE,
        related_name="activation_logs"
    )
    
    # Attempt details
    device_fingerprint = models.CharField(_("device fingerprint"), max_length=64, db_index=True)
    device_name = models.CharField(_("device name"), max_length=255, blank=True)
    device_info = models.JSONField(_("device info"), default=dict)
    ip_address = models.GenericIPAddressField(_("IP address"), db_index=True)
    user_agent = models.TextField(_("user agent"), blank=True)
    location = models.CharField(_("location"), max_length=255, blank=True)
    
    # Action details
    action = models.CharField(
        _("action"),
        max_length=20,
        choices=[
            ("ACTIVATE", "Activate"),
            ("VALIDATE", "Validate"),
            ("DEACTIVATE", "Deactivate"),
            ("REACTIVATE", "Reactivate"),
        ]
    )
    success = models.BooleanField(_("success"), default=False)
    error_message = models.TextField(_("error message"), blank=True)
    
    # Abuse detection
    is_suspicious = models.BooleanField(_("is suspicious"), default=False)
    suspicion_reason = models.TextField(_("suspicion reason"), blank=True)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("activation log")
        verbose_name_plural = _("activation logs")
        indexes = [
            models.Index(fields=["activation_code", "created_at"]),
            models.Index(fields=["device_fingerprint", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
            models.Index(fields=["is_suspicious", "created_at"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.action} - {self.activation_code.human_code} - {self.success}"

class RevocationLog(models.Model):
    """Log of code revocations."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activation_code = models.ForeignKey(
        ActivationCode,
        on_delete=models.CASCADE,
        related_name="revocation_logs"
    )
    
    # Revocation details
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="revocation_logs"
    )
    reason = models.TextField(_("reason"))
    details = models.JSONField(_("details"), default=dict)
    
    # Undo tracking
    undone = models.BooleanField(_("undone"), default=False)
    undone_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="undone_revocations"
    )
    undone_at = models.DateTimeField(_("undone at"), null=True, blank=True)
    undo_reason = models.TextField(_("undo reason"), blank=True)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("revocation log")
        verbose_name_plural = _("revocation logs")
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Revocation: {self.activation_code.human_code}"

class LicenseFeature(models.Model):
    """Features available for different license types."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    software = models.ForeignKey(
        "products.Software",
        on_delete=models.CASCADE,
        related_name="license_features"
    )
    
    # Feature details
    name = models.CharField(_("name"), max_length=100)
    code = models.CharField(
        _("feature code"),
        max_length=50,
        db_index=True,
        help_text=_("Internal code for this feature")
    )
    description = models.TextField(_("description"), blank=True)
    
    # Availability by license type
    available_in_trial = models.BooleanField(_("available in trial"), default=False)
    available_in_standard = models.BooleanField(_("available in standard"), default=True)
    available_in_premium = models.BooleanField(_("available in premium"), default=True)
    available_in_enterprise = models.BooleanField(_("available in enterprise"), default=True)
    
    # Restrictions
    requires_activation = models.BooleanField(_("requires activation"), default=True)
    max_usage = models.IntegerField(
        _("max usage"),
        null=True,
        blank=True,
        help_text=_("Maximum usage count (null for unlimited)")
    )
    
    is_active = models.BooleanField(_("active"), default=True)
    display_order = models.IntegerField(_("display order"), default=0)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    
    class Meta:
        verbose_name = _("license feature")
        verbose_name_plural = _("license features")
        ordering = ["display_order", "name"]
        unique_together = ["software", "code"]
    
    def __str__(self):
        return f"{self.software.name} - {self.name}"
    
    def is_available_for_license_type(self, license_type):
        """Check if feature is available for given license type."""
        mapping = {
            "TRIAL": self.available_in_trial,
            "STANDARD": self.available_in_standard,
            "PREMIUM": self.available_in_premium,
            "ENTERPRISE": self.available_in_enterprise,
        }
        return mapping.get(license_type.upper(), False)

class LicenseUsage(models.Model):
    """Track usage of licensed features."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activation_code = models.ForeignKey(
        ActivationCode,
        on_delete=models.CASCADE,
        related_name="usage_logs"
    )
    feature = models.ForeignKey(
        LicenseFeature,
        on_delete=models.CASCADE,
        related_name="usage_logs"
    )
    
    # Usage details
    usage_count = models.IntegerField(_("usage count"), default=1)
    usage_data = models.JSONField(
        _("usage data"),
        default=dict,
        help_text=_("Additional usage data")
    )
    
    # Device info
    device_fingerprint = models.CharField(_("device fingerprint"), max_length=64, db_index=True)
    ip_address = models.GenericIPAddressField(_("IP address"))
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    
    class Meta:
        verbose_name = _("license usage")
        verbose_name_plural = _("license usage logs")
        indexes = [
            models.Index(fields=["activation_code", "feature"]),
            models.Index(fields=["device_fingerprint", "created_at"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.activation_code.human_code} - {self.feature.name}"

class CodeBatch(models.Model):
    """Batch of activation codes generated together."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    software = models.ForeignKey(
        "products.Software",
        on_delete=models.CASCADE,
        related_name="code_batches"
    )
    
    # Batch details
    name = models.CharField(_("batch name"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    license_type = models.CharField(
        _("license type"),
        max_length=20,
        choices=ActivationCode.TYPE_CHOICES
    )
    
    # Generation settings
    count = models.IntegerField(_("count"))
    max_activations = models.IntegerField(_("max activations"), default=1)
    expires_in_days = models.IntegerField(_("expires in days"), default=365)
    prefix = models.CharField(
        _("prefix"),
        max_length=10,
        blank=True,
        help_text=_("Prefix for generated codes")
    )
    
    # Status
    is_used = models.BooleanField(_("used"), default=False)
    used_count = models.IntegerField(_("used count"), default=0)
    
    # Metadata
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="code_batches"
    )
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("code batch")
        verbose_name_plural = _("code batches")
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.name} - {self.software.name} ({self.count} codes)"
    
    @property
    def unused_count(self):
        return self.count - self.used_count
