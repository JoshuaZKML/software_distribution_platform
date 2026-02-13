# backend/apps/notifications/models.py
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import timedelta


class BroadcastEmail(models.Model):
    """Compose and send bulk emails to segmented audiences."""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENDING', 'Sending'),
        ('SENT', 'Sent'),
        ('CANCELLED', 'Cancelled'),
    ]
    AUDIENCE_CHOICES = [
        ('ALL', 'All Users'),
        ('ACTIVE', 'Active Users (last 30 days)'),
        ('PAID', 'Paying Customers'),
        ('ADMIN', 'Administrators'),
        ('CUSTOM', 'Custom Filter (JSON)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='broadcasts_created'
    )

    subject = models.CharField(_("subject"), max_length=255)
    plain_body = models.TextField(_("plain text body"))
    html_body = models.TextField(_("HTML body"))

    audience = models.CharField(
        _("audience"),
        max_length=20,
        choices=AUDIENCE_CHOICES,
        default='ALL'
    )
    custom_filter = models.JSONField(
        _("custom filter"),
        default=dict,
        blank=True,
        help_text=_("Stores Q filters as JSON (advanced).")
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT'
    )
    scheduled_at = models.DateTimeField(_("scheduled at"), null=True, blank=True)
    sent_at = models.DateTimeField(_("sent at"), null=True, blank=True)

    total_recipients = models.PositiveIntegerField(_("total recipients"), default=0)
    successful_sent = models.PositiveIntegerField(_("successful sends"), default=0)
    failed_sent = models.PositiveIntegerField(_("failed sends"), default=0)

    # ----- NEW FIELDS (added for batch tracking) -----
    total_batches = models.PositiveIntegerField(_("total batches"), default=0)
    completed_batches = models.PositiveIntegerField(_("completed batches"), default=0)
    # ------------------------------------------------

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("broadcast email")
        verbose_name_plural = _("broadcast emails")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} ({self.status})"

    def clean(self):
        """Validate model state transitions and custom filter structure."""
        # Prevent invalid status transitions (optional, but helpful)
        if self.pk:
            old = BroadcastEmail.objects.get(pk=self.pk)
            if old.status == 'SENT' and self.status != 'SENT':
                raise ValidationError("Cannot change status from 'SENT'.")
            if old.status == 'CANCELLED' and self.status != 'CANCELLED':
                raise ValidationError("Cannot change status from 'CANCELLED'.")
            if old.status == 'SENDING' and self.status not in ['SENT', 'CANCELLED']:
                raise ValidationError("Sending broadcast can only become 'SENT' or 'CANCELLED'.")

        # Validate custom_filter structure when audience is CUSTOM
        if self.audience == 'CUSTOM':
            if not isinstance(self.custom_filter, dict):
                raise ValidationError("custom_filter must be a JSON object (dict).")
            # Additional schema validation can be added here if needed

    def save(self, *args, **kwargs):
        self.full_clean()  # Ensure clean() is called on every save
        super().save(*args, **kwargs)

    def get_queryset(self):
        """
        Return User queryset based on audience selection.
        NOTE: This method is kept for backward compatibility.
        For production‑scale systems, consider moving this logic to a dedicated
        service layer (e.g., AudienceResolver) to decouple models from query building.
        """
        from backend.apps.accounts.models import User
        qs = User.objects.filter(is_active=True, email__isnull=False).exclude(email='')

        if self.audience == 'ACTIVE':
            qs = qs.filter(last_login__gte=timezone.now() - timedelta(days=30))
        elif self.audience == 'PAID':
            # Users who have at least one successful payment
            qs = qs.filter(payments__status='COMPLETED').distinct()
        elif self.audience == 'ADMIN':
            qs = qs.filter(role__in=['ADMIN', 'SUPER_ADMIN'])
        elif self.audience == 'CUSTOM' and self.custom_filter:
            # Advanced: you can implement JSON‑to‑Q filtering later
            pass
        return qs


class BroadcastRecipient(models.Model):
    """
    Tracks individual delivery status for each user in a broadcast.
    Enables idempotent sending, auditing, and failure recovery.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    broadcast = models.ForeignKey(
        BroadcastEmail,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='broadcast_recipients'
    )
    # New optional field to snapshot the email address at sending time
    email_snapshot = models.EmailField(
        _("email snapshot"),
        blank=True,
        null=True,
        help_text=_("Email address of the user at the moment the broadcast was sent")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('broadcast', 'user')
        indexes = [
            models.Index(fields=['broadcast', 'status']),
            # Added index on user for efficient reverse lookups
            models.Index(fields=['user']),
        ]
        verbose_name = _("broadcast recipient")
        verbose_name_plural = _("broadcast recipients")

    def __str__(self):
        return f"{self.broadcast.subject} - {self.user.email} ({self.status})"


class EmailTemplate(models.Model):
    """
    Database‑backed email templates with placeholders.
    Used by the centralised notification service.
    """
    code = models.SlugField(
        unique=True,
        help_text=_("Internal identifier, e.g., 'license_expiry', 'welcome_email'")
    )
    name = models.CharField(_("template name"), max_length=100)
    subject = models.CharField(_("subject"), max_length=255)
    plain_body = models.TextField(_("plain text body"))
    html_body = models.TextField(_("HTML body"))
    placeholders = models.JSONField(
        _("placeholders"),
        default=list,
        blank=True,
        help_text=_("List of allowed placeholders (for documentation)")
    )
    is_active = models.BooleanField(_("active"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("email template")
        verbose_name_plural = _("email templates")
        ordering = ['code']

    def __str__(self):
        return f"{self.code} – {self.name}"


class Notification(models.Model):
    """
    Represents a single notification to a user, across any channel.
    Used by the centralised notification service.
    """
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('in_app', 'In‑App'),
        ('push', 'Push'),  # for future
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)  # rendered content (plain text for email, message for in‑app)
    html_body = models.TextField(blank=True)  # only for email
    context = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Tracking fields (optional)
    tracking_id = models.UUIDField(null=True, blank=True, unique=True)  # for open/click tracking
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    clicked_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['tracking_id']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification {self.id} – {self.user.email} – {self.channel}"


class EmailTrackingEvent(models.Model):
    """
    Tracks email opens and clicks, linked to a Notification (or optionally a Broadcast).
    """
    EVENT_TYPES = [
        ('open', 'Open'),
        ('click', 'Click'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tracking_events'
    )
    broadcast = models.ForeignKey(
        BroadcastEmail,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tracking_events'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    email = models.EmailField()  # fallback
    event_type = models.CharField(max_length=10, choices=EVENT_TYPES)
    link_url = models.URLField(blank=True)  # for click events
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("email tracking event")
        verbose_name_plural = _("email tracking events")
        indexes = [
            models.Index(fields=['notification']),
            models.Index(fields=['broadcast']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_event_type_display()} – {self.email} @ {self.created_at}"