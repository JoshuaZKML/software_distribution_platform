import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinLengthValidator
from django.core.exceptions import ValidationError


class Ticket(models.Model):
    """Support ticket model."""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('pending_user', 'Pending User'),
        ('pending_internal', 'Pending Internal'),
        ('resolved', 'Resolved'),
        ('reopened', 'Reopened'),
        ('on_hold', 'On Hold'),
        ('closed', 'Closed'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    subject = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_tickets',
        limit_choices_to={'role__in': ['ADMIN', 'SUPER_ADMIN']}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['assigned_to', 'status']),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status
        self._original_assigned = self.assigned_to

    def __str__(self):
        return f"Ticket #{self.id}: {self.subject}"

    def save(self, *args, **kwargs):
        if self.status == 'resolved' and not self.resolved_at:
            self.resolved_at = timezone.now()
        if self.status == 'closed' and not self.closed_at:
            self.closed_at = timezone.now()
        if self.status not in ['resolved', 'closed'] and self.resolved_at:
            self.resolved_at = None
        super().save(*args, **kwargs)


class TicketMessage(models.Model):
    """Individual message within a ticket (conversation)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField(validators=[MinLengthValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    attachments = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message by {self.user.email} on {self.ticket.id}"


class TicketBan(models.Model):
    """Ban a user from creating new tickets."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ticket_bans'
    )
    reason = models.TextField()
    is_permanent = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='bans_issued'
    )

    class Meta:
        ordering = ['-created_at']

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