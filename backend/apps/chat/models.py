import uuid
import secrets
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import EmailValidator, MinLengthValidator
from django.core.exceptions import ValidationError
from django.db.models import Q


class ChatSession(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending (visitor waiting)'),
        ('active', 'Active (assigned to admin)'),
        ('closed', 'Closed'),
        ('banned', 'Banned'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visitor_name = models.CharField(max_length=100)
    visitor_email = models.EmailField(validators=[EmailValidator()])
    visitor_phone = models.CharField(max_length=17)  # E.164 format
    visitor_token = models.CharField(max_length=64, blank=True, default='')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_chats',
        limit_choices_to={'role__in': ['ADMIN', 'SUPER_ADMIN']}
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['visitor_email']),
            models.Index(fields=['ip_address']),
        ]

    def save(self, *args, **kwargs):
        if not self.visitor_token:
            self.visitor_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Chat {self.id} - {self.visitor_name} ({self.status})"


class ChatMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        help_text="Null if sent by visitor"
    )
    sender_name = models.CharField(max_length=100, blank=True, help_text="Visitor's name if not authenticated")
    content = models.TextField(validators=[MinLengthValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
        ]

    def __str__(self):
        return f"Message in {self.session.id} at {self.created_at}"


class ChatBan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(blank=True, null=True, db_index=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True, db_index=True)
    reason = models.TextField()
    is_permanent = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='chat_bans_issued'
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=Q(email__isnull=False) | Q(ip_address__isnull=False),
                name='chat_ban_email_or_ip_required'
            )
        ]

    def clean(self):
        if not self.is_permanent and not self.expires_at:
            raise ValidationError('Expiration date required for non‑permanent bans.')
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError('Expiration date must be in the future.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        if self.is_permanent:
            return True
        return self.expires_at and self.expires_at > timezone.now()