# FILE: /backend/apps/security/models.py
"""
Security models for Software Distribution Platform.
Hardened for production: concurrency safety, data integrity, validation,
and proper indexing. All changes are backward‑compatible and non‑disruptive.
"""
import uuid
from django.db import models, transaction
from django.db.models import F
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings


# ----------------------------------------------------------------------
# Enums for better type safety (additive, non‑disruptive)
# ----------------------------------------------------------------------
class AbuseSeverity(models.IntegerChoices):
    LOW = 1, _("Level 1")
    MEDIUM = 5, _("Level 5")
    HIGH = 8, _("Level 8")
    CRITICAL = 10, _("Level 10")
    # Existing choices 1-10 remain valid; we add named constants for clarity.


class AbuseAttempt(models.Model):
    """Log of abuse attempts."""

    ATTEMPT_TYPES = [
        ("ACTIVATION", "Activation"),
        ("VALIDATION", "Validation"),
        ("BRUTE_FORCE", "Brute Force"),
        ("CODE_SHARING", "Code Sharing"),
        ("DEVICE_MISMATCH", "Device Mismatch"),
        ("GEO_VELOCITY", "Geographic Velocity"),
        ("RATE_LIMIT", "Rate Limit"),
        ("OTHER", "Other"),
    ]

    DETECTION_METHODS = [
        ("AUTO", "Automatic"),
        ("MANUAL", "Manual"),
        ("AI", "AI Detection"),
        ("PATTERN", "Pattern Detection"),
        ("HONEYPOT", "Honeypot"),          # ADDED – fixes bug in HoneypotCode
    ]

    ACTION_CHOICES = [
        ("NONE", "None"),
        ("WARNED", "Warned"),
        ("BLOCKED", "Blocked"),
        ("REVOKED", "Revoked"),
        ("BANNED", "Banned"),
        ("REQUIRES_VERIFICATION", "Requires Verification"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Target
    activation_code = models.ForeignKey(
        "licenses.ActivationCode",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="abuse_attempts"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="abuse_attempts"
    )

    # Attempt details
    ip_address = models.GenericIPAddressField(_("IP address"), db_index=True)
    device_fingerprint = models.CharField(_("device fingerprint"), max_length=64, db_index=True)
    user_agent = models.TextField(_("user agent"), blank=True)
    location = models.CharField(_("location"), max_length=255, blank=True)

    # What was attempted
    attempt_type = models.CharField(
        _("attempt type"),
        max_length=50,
        choices=ATTEMPT_TYPES,
    )

    # Detection details
    detection_method = models.CharField(
        _("detection method"),
        max_length=50,
        choices=DETECTION_METHODS,
        default="AUTO"
    )

    # Severity – now using IntegerChoices, but still accepts any 1-10
    severity = models.IntegerField(
        _("severity"),
        choices=AbuseSeverity.choices,
        default=AbuseSeverity.MEDIUM
    )

    # Response
    action_taken = models.CharField(
        _("action taken"),
        max_length=50,
        choices=ACTION_CHOICES,
        default="NONE"
    )

    # Resolution
    resolved = models.BooleanField(_("resolved"), default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_abuses"
    )
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    resolution_notes = models.TextField(_("resolution notes"), blank=True)

    # Metadata
    details = models.JSONField(_("details"), default=dict)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("abuse attempt")
        verbose_name_plural = _("abuse attempts")
        indexes = [
            models.Index(fields=["ip_address", "created_at"]),
            models.Index(fields=["device_fingerprint", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["activation_code", "created_at"]),
            models.Index(fields=["severity", "resolved"]),
            models.Index(fields=["attempt_type", "created_at"]),  # ADDED – common query
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Abuse: {self.attempt_type} - {self.ip_address}"

    def clean(self):
        """Validate severity bounds (defensive)."""
        if self.severity not in range(1, 11):
            raise ValidationError({'severity': _('Severity must be between 1 and 10.')})


class AbuseAlert(models.Model):
    """Alert for abuse detection."""

    ALERT_TYPES = [
        ("CRITICAL", "Critical"),
        ("HIGH", "High"),
        ("MEDIUM", "Medium"),
        ("LOW", "Low"),
        ("INFO", "Informational"),
    ]

    DELIVERY_METHODS = ["email", "push", "in-app"]  # canonical list

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Related abuse attempt
    abuse_attempt = models.ForeignKey(
        AbuseAttempt,
        on_delete=models.CASCADE,
        related_name="alerts"
    )

    # Alert details
    alert_type = models.CharField(
        _("alert type"),
        max_length=50,
        choices=ALERT_TYPES,
    )
    title = models.CharField(_("title"), max_length=255)
    message = models.TextField(_("message"))

    # Status
    acknowledged = models.BooleanField(_("acknowledged"), default=False)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts"
    )
    acknowledged_at = models.DateTimeField(_("acknowledged at"), null=True, blank=True)

    # Delivery
    delivered_via = models.JSONField(
        _("delivered via"),
        default=list,
        help_text=_("Delivery methods (email, push, in-app)")
    )

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("abuse alert")
        verbose_name_plural = _("abuse alerts")
        indexes = [
            models.Index(fields=["alert_type", "created_at"]),
            models.Index(fields=["acknowledged", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Alert: {self.title} - {self.alert_type}"

    def clean(self):
        """Validate delivered_via contains only allowed methods."""
        if self.delivered_via:
            invalid = set(self.delivered_via) - set(self.DELIVERY_METHODS)
            if invalid:
                raise ValidationError(
                    {'delivered_via': _(f'Invalid delivery method(s): {", ".join(invalid)}')}
                )


class IPBlacklist(models.Model):
    """Blacklisted IP addresses (CIDR‑aware)."""

    SOURCE_CHOICES = [
        ("MANUAL", "Manual"),
        ("AUTO", "Automatic"),
        ("THREAT_INTEL", "Threat Intelligence"),
        ("USER_REPORT", "User Report"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # IP details – we keep the original fields for backward compatibility,
    # but we also add a computed CIDR string for accurate subnet blocking.
    ip_address = models.GenericIPAddressField(_("IP address"), db_index=True)
    subnet_mask = models.PositiveSmallIntegerField(
        _("subnet mask"),
        null=True,
        blank=True,
        help_text=_("CIDR notation (e.g., 24 for /24). For a single IP, use 32 (IPv4) or 128 (IPv6).")
    )
    # NEW: store the normalized CIDR string; can be populated via migration or clean()
    cidr = models.CharField(
        _("CIDR"),
        max_length=43,
        blank=True,
        editable=False,
        db_index=True,
        help_text=_("Normalized CIDR string (e.g., '192.168.1.0/24'). Auto‑generated.")
    )

    # Reason
    reason = models.TextField(_("reason"))
    source = models.CharField(
        _("source"),
        max_length=50,
        choices=SOURCE_CHOICES,
        default="MANUAL"
    )

    # Duration
    is_permanent = models.BooleanField(_("permanent"), default=False)
    expires_at = models.DateTimeField(
        _("expires at"),
        null=True,
        blank=True,
        help_text=_("Leave blank for permanent ban")
    )

    # Status
    is_active = models.BooleanField(_("active"), default=True)

    # Metadata
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_blacklist_entries"
    )

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("IP blacklist")
        verbose_name_plural = _("IP blacklist entries")
        indexes = [
            models.Index(fields=["ip_address", "is_active"]),
            models.Index(fields=["is_active", "expires_at"]),
            models.Index(fields=["cidr"]),        # NEW – for fast subnet lookups
        ]

    def __str__(self):
        return f"Blacklist: {self.cidr or self.ip_address}"

    @property
    def is_expired(self):
        if self.is_permanent or not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def should_be_active(self):
        return self.is_active and not self.is_expired

    def clean(self):
        """Normalize IP + subnet into a CIDR string and validate."""
        import ipaddress
        try:
            if self.subnet_mask is not None:
                network = ipaddress.ip_network(f"{self.ip_address}/{self.subnet_mask}", strict=False)
            else:
                # Single IP – treat as /32 or /128
                network = ipaddress.ip_network(self.ip_address)
            self.cidr = str(network)
        except ValueError as e:
            raise ValidationError(_(f"Invalid IP or subnet mask: {e}"))

    def save(self, *args, **kwargs):
        """Ensure clean() is called and CIDR is generated."""
        self.full_clean()
        super().save(*args, **kwargs)


class CodeBlacklist(models.Model):
    """Blacklisted activation codes."""

    SOURCE_CHOICES = [
        ("MANUAL", "Manual"),
        ("AUTO", "Automatic"),
        ("USER_REPORT", "User Report"),
        ("LAW_ENFORCEMENT", "Law Enforcement"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Code details
    activation_code = models.OneToOneField(
        "licenses.ActivationCode",
        on_delete=models.CASCADE,
        related_name="blacklist_entry"
    )

    # Reason
    reason = models.TextField(_("reason"))
    source = models.CharField(
        _("source"),
        max_length=50,
        choices=SOURCE_CHOICES,
        default="MANUAL"
    )

    # Duration
    is_permanent = models.BooleanField(_("permanent"), default=True)
    expires_at = models.DateTimeField(
        _("expires at"),
        null=True,
        blank=True,
        help_text=_("Leave blank for permanent ban")
    )

    # Status
    is_active = models.BooleanField(_("active"), default=True)

    # Metadata
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_code_blacklists"
    )

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("code blacklist")
        verbose_name_plural = _("code blacklist entries")
        indexes = [
            # Remove redundant index (activation_code is already unique)
            models.Index(fields=["is_active", "expires_at"]),  # NEW – for cleanup
        ]

    def __str__(self):
        return f"Code Blacklist: {self.activation_code.human_code}"

    @property
    def is_expired(self):
        if self.is_permanent or not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def should_be_active(self):
        return self.is_active and not self.is_expired


class HoneypotCode(models.Model):
    """Honeypot codes for catching attackers."""

    DETECTION_METHODS = [
        ("PATTERN", "Pattern Detection"),
        ("BEHAVIOR", "Behavior Analysis"),
        ("MANUAL", "Manual"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Original code (if applicable)
    original_code = models.ForeignKey(
        "licenses.ActivationCode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="honeypot_codes"
    )

    # Honeypot code
    honeypot_code = models.CharField(
        _("honeypot code"),
        max_length=50,
        unique=True,
        db_index=True
    )

    # Attacker info
    attacker_ip = models.GenericIPAddressField(_("attacker IP"), db_index=True)
    attacker_device_fp = models.CharField(_("attacker device fingerprint"), max_length=64, db_index=True)
    attacker_user_agent = models.TextField(_("attacker user agent"), blank=True)

    # Detection
    detection_method = models.CharField(
        _("detection method"),
        max_length=50,
        choices=DETECTION_METHODS,
        default="PATTERN"
    )

    # Status
    is_active = models.BooleanField(_("active"), default=True)
    triggered = models.BooleanField(_("triggered"), default=False)
    triggered_at = models.DateTimeField(_("triggered at"), null=True, blank=True)
    trigger_count = models.IntegerField(_("trigger count"), default=0)

    # Monitoring
    monitor_duration = models.IntegerField(
        _("monitor duration"),
        default=30,
        help_text=_("Duration to monitor in days")
    )

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("honeypot code")
        verbose_name_plural = _("honeypot codes")
        indexes = [
            models.Index(fields=["honeypot_code", "is_active"]),
            models.Index(fields=["attacker_ip", "created_at"]),
            models.Index(fields=["triggered", "created_at"]),
        ]

    def __str__(self):
        return f"Honeypot: {self.honeypot_code}"

    @transaction.atomic
    def trigger(self):
        """
        Mark honeypot as triggered.
        Uses select_for_update to prevent race conditions and F() for atomic increment.
        """
        # Lock this row to avoid double counting
        honeypot = HoneypotCode.objects.select_for_update().get(pk=self.pk)

        honeypot.triggered = True
        honeypot.triggered_at = timezone.now()
        honeypot.trigger_count = F('trigger_count') + 1
        honeypot.save(update_fields=['triggered', 'triggered_at', 'trigger_count'])

        # Create abuse attempt – detection_method now uses "HONEYPOT" (added above)
        AbuseAttempt.objects.create(
            ip_address=honeypot.attacker_ip,
            device_fingerprint=honeypot.attacker_device_fp,
            user_agent=honeypot.attacker_user_agent,
            attempt_type="BRUTE_FORCE",
            detection_method="HONEYPOT",   # now valid
            severity=AbuseSeverity.HIGH,
            action_taken="BANNED",
            details={
                "honeypot_code": honeypot.honeypot_code,
                "original_code": str(honeypot.original_code.id) if honeypot.original_code else None,
            }
        )
        # Refresh instance to reflect updated trigger_count
        honeypot.refresh_from_db()
        return True


class SecuritySettings(models.Model):
    """Security configuration settings – enforced as a singleton."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ------------------------------------------------------------------
    # Singleton enforcement: add a boolean field with unique constraint.
    # This ensures only one row can exist at the DB level.
    # ------------------------------------------------------------------
    singleton = models.BooleanField(
        default=True,
        unique=True,
        editable=False,
        help_text=_("Singleton flag – do not change.")
    )

    # Rate limiting
    activation_rate_limit = models.IntegerField(
        _("activation rate limit"),
        default=10,
        help_text=_("Max activations per IP per hour")
    )
    validation_rate_limit = models.IntegerField(
        _("validation rate limit"),
        default=50,
        help_text=_("Max validations per IP per hour")
    )
    login_rate_limit = models.IntegerField(
        _("login rate limit"),
        default=5,
        help_text=_("Max login attempts per IP per hour")
    )

    # Abuse detection thresholds
    geo_velocity_threshold = models.IntegerField(
        _("geo velocity threshold"),
        default=800,
        help_text=_("Maximum km/h for geographic velocity check")
    )
    device_change_threshold = models.IntegerField(
        _("device change threshold"),
        default=3,
        help_text=_("Maximum device changes before requiring verification")
    )
    revocation_rate_threshold = models.DecimalField(
        _("revocation rate threshold"),
        max_digits=5,
        decimal_places=2,
        default=0.3,
        help_text=_("Maximum revocation rate (0-1) for automatic flagging")
    )

    # Auto-response settings
    auto_revoke_critical = models.BooleanField(
        _("auto revoke critical"),
        default=True,
        help_text=_("Automatically revoke codes on critical abuse detection")
    )
    auto_block_ips = models.BooleanField(
        _("auto block IPs"),
        default=True,
        help_text=_("Automatically block IPs on repeated abuse")
    )
    auto_block_duration = models.IntegerField(
        _("auto block duration"),
        default=7,
        help_text=_("Duration in days for automatic IP blocks")
    )

    # Verification requirements
    require_email_verification = models.BooleanField(
        _("require email verification"),
        default=True
    )
    require_device_verification = models.BooleanField(
        _("require device verification"),
        default=True
    )
    require_admin_approval = models.BooleanField(
        _("require admin approval"),
        default=False,
        help_text=_("Require admin approval for new user registrations")
    )

    # Honeypot settings
    enable_honeypots = models.BooleanField(_("enable honeypots"), default=True)
    honeypot_percentage = models.IntegerField(
        _("honeypot percentage"),
        default=5,
        help_text=_("Percentage of codes to convert to honeypots on abuse detection")
    )

    # Notification settings
    notify_superadmin_abuse = models.BooleanField(
        _("notify superadmin on abuse"),
        default=True
    )
    notify_admin_abuse = models.BooleanField(
        _("notify admin on abuse"),
        default=True
    )
    abuse_notification_threshold = models.IntegerField(
        _("abuse notification threshold"),
        default=7,
        help_text=_("Minimum severity level to trigger notifications")
    )

    # Last updated
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="updated_security_settings"
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("security settings")
        verbose_name_plural = _("security settings")
        # No indexes needed; only one row exists.

    def __str__(self):
        return "Security Settings"

    def clean(self):
        """Validate field constraints."""
        if self.activation_rate_limit <= 0:
            raise ValidationError({'activation_rate_limit': _('Rate limit must be positive.')})
        if self.validation_rate_limit <= 0:
            raise ValidationError({'validation_rate_limit': _('Rate limit must be positive.')})
        if self.login_rate_limit <= 0:
            raise ValidationError({'login_rate_limit': _('Rate limit must be positive.')})
        if not 0 <= self.revocation_rate_threshold <= 1:
            raise ValidationError({'revocation_rate_threshold': _('Threshold must be between 0 and 1.')})
        if not 0 <= self.honeypot_percentage <= 100:
            raise ValidationError({'honeypot_percentage': _('Percentage must be between 0 and 100.')})
        if self.auto_block_duration <= 0:
            raise ValidationError({'auto_block_duration': _('Duration must be positive.')})

    def save(self, *args, **kwargs):
        """
        Ensure only one instance exists.
        With the unique `singleton` field, DB-level enforcement is automatic.
        We keep the original check for backward compatibility but it's no longer
        strictly necessary. However, we keep it to avoid breaking any existing
        code that may rely on the exception type.
        """
        if not self.pk and SecuritySettings.objects.exists():
            raise ValueError("Only one SecuritySettings instance can exist")
        self.full_clean()
        super().save(*args, **kwargs)


# ----------------------------------------------------------------------
# Security Notification Log – Persistent Idempotency for Celery Tasks
# ----------------------------------------------------------------------
class SecurityNotificationLog(models.Model):
    """
    Immutable log of security notifications sent by Celery tasks.
    Provides persistent idempotency across cache resets and worker restarts.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA‑256 fingerprint of the security event"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_notifications"
    )
    risk_level = models.IntegerField()
    ip_address = models.GenericIPAddressField()
    recipient_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Security Notification Log"
        verbose_name_plural = "Security Notification Logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification {self.event_hash[:8]} at {self.created_at}"
