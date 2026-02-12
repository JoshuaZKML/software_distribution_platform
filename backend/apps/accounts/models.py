"""
Accounts models for Software Distribution Platform.
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import hashlib
import json

class UserManager(BaseUserManager):
    """Custom user manager for User model."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        if not email:
            raise ValueError("The Email field must be set")
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.SUPER_ADMIN)
        extra_fields.setdefault("is_verified", True)
        
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if extra_fields.get("role") != User.Role.SUPER_ADMIN:
            raise ValueError("Superuser must have role=SUPER_ADMIN.")
        
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model with role-based permissions."""
    
    class Role(models.TextChoices):
        USER = "USER", _("User")
        ADMIN = "ADMIN", _("Admin")
        SUPER_ADMIN = "SUPER_ADMIN", _("Super Admin")
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True, db_index=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
        db_index=True
    )
    
    # Personal info
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    company = models.CharField(_("company"), max_length=255, blank=True)
    phone = models.CharField(_("phone number"), max_length=20, blank=True)
    
    # Security - ENHANCED WITH 2FA
    hardware_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text=_("SHA-256 hash of device fingerprint")
    )
    
    # MFA Configuration (using existing fields with enhancements)
    mfa_enabled = models.BooleanField(_("MFA enabled"), default=False)
    mfa_secret = models.CharField(
        max_length=32, 
        blank=True, 
        null=True,
        help_text=_("TOTP secret key for emergency 2FA")
    )
    
    # NEW: Emergency 2FA specific fields
    mfa_backup_codes = models.JSONField(
        _("MFA backup codes"),
        default=list,
        blank=True,
        help_text=_("Emergency backup codes (10 total)")
    )
    mfa_emergency_only = models.BooleanField(
        _("MFA emergency only"),
        default=True,
        help_text=_("2FA only required for suspicious logins")
    )
    mfa_last_used = models.DateTimeField(
        _("MFA last used"),
        null=True, 
        blank=True
    )
    
    last_device_change = models.DateTimeField(_("last device change"), null=True, blank=True)
    
    # Status flags
    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("staff status"), default=False)
    is_verified = models.BooleanField(_("verified"), default=False)
    is_blocked = models.BooleanField(_("blocked"), default=False)
    blocked_reason = models.TextField(_("blocked reason"), blank=True)
    blocked_at = models.DateTimeField(_("blocked at"), null=True, blank=True)
    blocked_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blocked_users"
    )
    
    # Timestamps
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    last_login = models.DateTimeField(_("last login"), null=True, blank=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    
    # IP tracking
    last_login_ip = models.GenericIPAddressField(_("last login IP"), null=True, blank=True)
    registration_ip = models.GenericIPAddressField(_("registration IP"), null=True, blank=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    
    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["date_joined"]),
        ]
    
    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
    
    def get_full_name(self):
        """Return the full name for the user."""
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip() or self.email
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.email.split("@")[0]
    
    @property
    def is_super_admin(self):
        """Check if user is Super Admin."""
        return self.role == self.Role.SUPER_ADMIN
    
    @property
    def is_admin(self):
        """Check if user is Admin."""
        return self.role == self.Role.ADMIN
    
    @property
    def is_regular_user(self):
        """Check if user is regular User."""
        return self.role == self.Role.USER
    
    def generate_device_fingerprint(self, request):
        """Generate device fingerprint from request."""
        components = [
            request.META.get("HTTP_USER_AGENT", ""),
            request.META.get("HTTP_ACCEPT_LANGUAGE", ""),
            request.META.get("REMOTE_ADDR", ""),
        ]
        fingerprint_string = "|".join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    def can_impersonate(self):
        """Check if user can impersonate other users."""
        return self.is_super_admin or (self.is_admin and self.has_perm("accounts.can_impersonate"))
    
    # ============================================================================
    # EMERGENCY 2FA METHODS (NEW - Safe additions)
    # ============================================================================
    
    def enable_emergency_mfa(self):
        """Enable emergency MFA with TOTP."""
        try:
            import pyotp
            import secrets
            
            # Generate TOTP secret
            self.mfa_secret = pyotp.random_base32()
            
            # Generate 10 backup codes
            self.mfa_backup_codes = [
                secrets.token_urlsafe(8).upper() for _ in range(10)
            ]
            
            self.mfa_enabled = True
            self.mfa_emergency_only = True  # Emergency-only by default
            self.save()
            
            return self.mfa_secret
            
        except ImportError:
            raise ImportError("pyotp package is required for MFA. Install with: pip install pyotp")
    
    def verify_mfa_code(self, code):
        """Verify MFA code (TOTP or backup code)."""
        if not self.mfa_enabled or not self.mfa_secret:
            return False
        
        try:
            import pyotp
            
            # 1. Check if it's a backup code
            if code in self.mfa_backup_codes:
                # Remove used backup code
                self.mfa_backup_codes.remove(code)
                self.save()
                self._log_mfa_usage('backup_code')
                return True
            
            # 2. Check if it's a TOTP code
            totp = pyotp.TOTP(self.mfa_secret)
            if totp.verify(code, valid_window=1):  # Allow 30s window
                self.mfa_last_used = timezone.now()
                self.save()
                self._log_mfa_usage('totp')
                return True
            
            return False
            
        except ImportError:
            raise ImportError("pyotp package is required for MFA")
    
    def get_mfa_provisioning_uri(self, issuer_name="Software Distribution Platform"):
        """Get QR code URI for authenticator apps."""
        if not self.mfa_secret:
            return None
        
        try:
            import pyotp
            return pyotp.totp.TOTP(self.mfa_secret).provisioning_uri(
                name=self.email,
                issuer_name=issuer_name
            )
        except ImportError:
            return None
    
    def disable_mfa(self):
        """Disable MFA completely."""
        self.mfa_enabled = False
        self.mfa_secret = None
        self.mfa_backup_codes = []
        self.mfa_emergency_only = False
        self.save()
    
    def regenerate_backup_codes(self):
        """Regenerate backup codes."""
        if not self.mfa_enabled:
            return []
        
        import secrets
        self.mfa_backup_codes = [
            secrets.token_urlsafe(8).upper() for _ in range(10)
        ]
        self.save()
        return self.mfa_backup_codes
    
    def get_mfa_status(self):
        """Get MFA status information."""
        return {
            'enabled': self.mfa_enabled,
            'emergency_only': self.mfa_emergency_only,
            'has_secret': bool(self.mfa_secret),
            'backup_codes_remaining': len(self.mfa_backup_codes),
            'last_used': self.mfa_last_used,
            'provisioning_uri': self.get_mfa_provisioning_uri() if self.mfa_secret else None
        }
    
    def _log_mfa_usage(self, method):
        """Internal method to log MFA usage (for SecurityLog integration)."""
        # This would integrate with your existing SecurityLog model
        # Implementation depends on your SecurityLog setup
        pass

class AdminProfile(models.Model):
    """Extended profile for Admin users."""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="admin_profile"
    )
    
    # Permissions
    can_manage_users = models.BooleanField(_("can manage users"), default=False)
    can_manage_licenses = models.BooleanField(_("can manage licenses"), default=True)
    can_manage_payments = models.BooleanField(_("can manage payments"), default=True)
    can_manage_software = models.BooleanField(_("can manage software"), default=True)
    can_view_reports = models.BooleanField(_("can view reports"), default=True)
    can_impersonate = models.BooleanField(_("can impersonate users"), default=False)
    
    # Limits
    max_users = models.IntegerField(_("max users"), default=100, help_text=_("Maximum users this admin can manage"))
    max_licenses = models.IntegerField(_("max licenses"), default=1000, help_text=_("Maximum licenses this admin can generate"))
    
    # Notification preferences
    email_notifications = models.BooleanField(_("email notifications"), default=True)
    push_notifications = models.BooleanField(_("push notifications"), default=True)
    
    # Metadata
    department = models.CharField(_("department"), max_length=100, blank=True)
    position = models.CharField(_("position"), max_length=100, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    
    class Meta:
        verbose_name = _("admin profile")
        verbose_name_plural = _("admin profiles")
    
    def __str__(self):
        return f"Admin Profile: {self.user.email}"
    
    @property
    def permissions_list(self):
        """Return list of enabled permissions."""
        permissions = []
        if self.can_manage_users:
            permissions.append("manage_users")
        if self.can_manage_licenses:
            permissions.append("manage_licenses")
        if self.can_manage_payments:
            permissions.append("manage_payments")
        if self.can_manage_software:
            permissions.append("manage_software")
        if self.can_view_reports:
            permissions.append("view_reports")
        if self.can_impersonate:
            permissions.append("impersonate")
        return permissions

class UserSession(models.Model):
    """Track user sessions for security."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sessions"
    )
    session_key = models.CharField(_("session key"), max_length=40, db_index=True)
    device_fingerprint = models.CharField(_("device fingerprint"), max_length=64, db_index=True)
    ip_address = models.GenericIPAddressField(_("IP address"))
    user_agent = models.TextField(_("user agent"), blank=True)
    location = models.CharField(_("location"), max_length=255, blank=True)
    
    # Status
    is_active = models.BooleanField(_("active"), default=True)
    last_activity = models.DateTimeField(_("last activity"), auto_now=True)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("user session")
        verbose_name_plural = _("user sessions")
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["device_fingerprint"]),
            models.Index(fields=["last_activity"]),
        ]
    
    def __str__(self):
        return f"Session: {self.user.email} - {self.device_fingerprint[:8]}"

class DeviceChangeLog(models.Model):
    """Log device changes for users."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="device_changes"
    )
    old_fingerprint = models.CharField(_("old fingerprint"), max_length=64)
    new_fingerprint = models.CharField(_("new fingerprint"), max_length=64)
    ip_address = models.GenericIPAddressField(_("IP address"))
    user_agent = models.TextField(_("user agent"))
    
    # Verification
    verification_token = models.CharField(_("verification token"), max_length=64, blank=True)
    verified = models.BooleanField(_("verified"), default=False)
    verified_at = models.DateTimeField(_("verified at"), null=True, blank=True)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("device change log")
        verbose_name_plural = _("device change logs")
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Device change: {self.user.email}"

class AdminActionLog(models.Model):
    """Log all admin actions for audit purposes."""
    
    ACTION_TYPES = [
        ("USER_CREATED", "User created"),
        ("USER_UPDATED", "User updated"),
        ("USER_DELETED", "User deleted"),
        ("USER_BLOCKED", "User blocked"),
        ("USER_UNBLOCKED", "User unblocked"),
        ("LICENSE_GENERATED", "License generated"),
        ("LICENSE_REVOKED", "License revoked"),
        ("LICENSE_UPDATED", "License updated"),
        ("PAYMENT_APPROVED", "Payment approved"),
        ("PAYMENT_REJECTED", "Payment rejected"),
        ("SOFTWARE_ADDED", "Software added"),
        ("SOFTWARE_UPDATED", "Software updated"),
        ("SOFTWARE_DELETED", "Software deleted"),
        ("SETTINGS_UPDATED", "Settings updated"),
        ("ACTION_UNDONE", "Action undone"),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="actions"
    )
    action_type = models.CharField(_("action type"), max_length=50, choices=ACTION_TYPES)
    target_id = models.UUIDField(_("target ID"), null=True, blank=True)
    target_type = models.CharField(_("target type"), max_length=100, blank=True)
    
    # Details
    details = models.JSONField(_("details"), default=dict)
    ip_address = models.GenericIPAddressField(_("IP address"))
    user_agent = models.TextField(_("user agent"), blank=True)
    
    # Undo tracking
    reversed = models.BooleanField(_("reversed"), default=False)
    undo_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="undone_actions"
    )
    undo_at = models.DateTimeField(_("undo at"), null=True, blank=True)
    undo_reason = models.TextField(_("undo reason"), blank=True)
    
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    
    class Meta:
        verbose_name = _("admin action log")
        verbose_name_plural = _("admin action logs")
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["target_id", "target_type"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.get_action_type_display()} by {self.user.email if self.user else 'System'}"
    
    def can_be_undone(self):
        """Check if this action can be undone."""
        undoable_actions = [
            "USER_BLOCKED",
            "USER_DELETED",
            "LICENSE_REVOKED",
            "PAYMENT_REJECTED",
            "SOFTWARE_DELETED",
        ]
        return (
            not self.reversed and
            self.action_type in undoable_actions and
            (timezone.now() - self.created_at).total_seconds() < 86400  # 24 hours
        )