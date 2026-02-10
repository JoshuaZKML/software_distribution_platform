"""
Security models for Software Distribution Platform.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings

class AbuseAttempt(models.Model):
    """Log of abuse attempts."""
    
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
        choices=[
            ("ACTIVATION", "Activation"),
            ("VALIDATION", "Validation"),
            ("BRUTE_FORCE", "Brute Force"),
            ("CODE_SHARING", "Code Sharing"),
            ("DEVICE_MISMATCH", "Device Mismatch"),
            ("GEO_VELOCITY", "Geographic Velocity"),
            ("RATE_LIMIT", "Rate Limit"),
            ("OTHER", "Other"),
        ]
    )
    
    # Detection details
    detection_method = models.CharField(
        _("detection method"),
        max_length=50,
        choices=[
            ("AUTO", "Automatic"),
            ("MANUAL", "Manual"),
            ("AI", "AI Detection"),
            ("PATTERN", "Pattern Detection"),
        ],
        default="AUTO"
    )
    
    # Severity
    severity = models.IntegerField(
        _("severity"),
        choices=[(i, f"Level {i}") for i in range(1, 11)],
        default=5
    )
    
    # Response
    action_taken = models.CharField(
        _("action taken"),
        max_length=50,
        choices=[
            ("NONE", "None"),
            ("WARNED", "Warned"),
            ("BLOCKED", "Blocked"),
            ("REVOKED", "Revoked"),
            ("BANNED", "Banned"),
            ("REQUIRES_VERIFICATION", "Requires Verification"),
        ],
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
        ]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Abuse: {self.attempt_type} - {self.ip_address}"

class AbuseAlert(models.Model):
    """Alert for abuse detection."""
    
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
        choices=[
            ("CRITICAL", "Critical"),
            ("HIGH", "High"),
            ("MEDIUM", "Medium"),
            ("LOW", "Low"),
            ("INFO", "Informational"),
        ]
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

class IPBlacklist(models.Model):
    """Blacklisted IP addresses."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # IP details
    ip_address = models.GenericIPAddressField(_("IP address"), unique=True, db_index=True)
    subnet_mask = models.PositiveSmallIntegerField(
        _("subnet mask"),
        null=True,
        blank=True,
        help_text=_("CIDR notation (e.g., 24 for /24)")
    )
    
    # Reason
    reason = models.TextField(_("reason"))
    source = models.CharField(
        _("source"),
        max_length=50,
        choices=[
            ("MANUAL", "Manual"),
            ("AUTO", "Automatic"),
            ("THREAT_INTEL", "Threat Intelligence"),
            ("USER_REPORT", "User Report"),
        ],
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
        verbose_name_plural = _("IP blacklist")
        indexes = [
            models.Index(fields=["ip_address", "is_active"]),
            models.Index(fields=["is_active", "expires_at"]),
        ]
    
    def __str__(self):
        return f"Blacklist: {self.ip_address}"
    
    @property
    def is_expired(self):
        if self.is_permanent or not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def should_be_active(self):
        return self.is_active and not self.is_expired

class CodeBlacklist(models.Model):
    """Blacklisted activation codes."""
    
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
        choices=[
            ("MANUAL", "Manual"),
            ("AUTO", "Automatic"),
            ("USER_REPORT", "User Report"),
            ("LAW_ENFORCEMENT", "Law Enforcement"),
        ],
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
        verbose_name_plural = _("code blacklist")
        indexes = [
            models.Index(fields=["activation_code", "is_active"]),
        ]
    
    def __str__(self):
        return f"Code Blacklist: {self.activation_code.human_code}"

class HoneypotCode(models.Model):
    """Honeypot codes for catching attackers."""
    
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
        choices=[
            ("PATTERN", "Pattern Detection"),
            ("BEHAVIOR", "Behavior Analysis"),
            ("MANUAL", "Manual"),
            ("OTHER", "Other"),
        ]
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
    
    def trigger(self):
        """Mark honeypot as triggered."""
        self.triggered = True
        self.triggered_at = timezone.now()
        self.trigger_count += 1
        self.save()
        
        # Create abuse attempt
        AbuseAttempt.objects.create(
            ip_address=self.attacker_ip,
            device_fingerprint=self.attacker_device_fp,
            user_agent=self.attacker_user_agent,
            attempt_type="BRUTE_FORCE",
            detection_method="HONEYPOT",
            severity=8,
            action_taken="BANNED",
            details={
                "honeypot_code": self.honeypot_code,
                "original_code": str(self.original_code.id) if self.original_code else None,
            }
        )
        
        return True

class SecuritySettings(models.Model):
    """Security configuration settings."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
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
    
    def __str__(self):
        return "Security Settings"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and SecuritySettings.objects.exists():
            raise ValueError("Only one SecuritySettings instance can exist")
        super().save(*args, **kwargs)
