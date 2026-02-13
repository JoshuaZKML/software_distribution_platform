# backend/apps/notifications/admin.py
import logging
from django.contrib import admin
from django.urls import reverse, path
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.html import format_html
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import PermissionDenied
from .models import BroadcastEmail, BroadcastRecipient, EmailTemplate  # Added new models
from .tasks import send_broadcast_email

logger = logging.getLogger(__name__)


@admin.register(BroadcastEmail)
class BroadcastEmailAdmin(admin.ModelAdmin):
    list_display = ['subject', 'audience', 'status', 'scheduled_at', 'sent_at',
                    'total_recipients', 'successful_sent', 'failed_sent', 'actions_column']
    list_filter = ['status', 'audience', 'created_at']
    readonly_fields = [
    'status', 'sent_at', 'total_recipients', 'successful_sent', 'failed_sent',
    'created_at', 'updated_at'
]
    fieldsets = (
        ('Content', {
            'fields': ('subject', 'plain_body', 'html_body')
        }),
        ('Audience', {
            'fields': ('audience', 'custom_filter', 'scheduled_at')
        }),
        ('Status', {
            'fields': ('status', 'sent_at', 'total_recipients', 'successful_sent', 'failed_sent')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )

    def actions_column(self, obj):
        """Render a 'Send Now' button for draft broadcasts."""
        if obj.status == 'DRAFT':
            # The link now goes to a confirmation page instead of direct action
            url = reverse('admin:notifications_broadcastemail_send_confirm', args=[obj.id])
            return format_html('<a class="button" href="{}">Send Now</a>', url)
        return "-"
    actions_column.short_description = 'Actions'

    def save_model(self, request, obj, form, change):
        """Auto‑assign created_by if not set."""
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_send_permission(self, request):
        """Only superusers or users with a specific permission can send broadcasts."""
        return request.user.is_superuser or request.user.has_perm('notifications.can_send_broadcast')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:pk>/send/',
                self.admin_site.admin_view(self.send_now),
                name='notifications_broadcastemail_send',
            ),
            path(
                '<uuid:pk>/send/confirm/',
                self.admin_site.admin_view(self.send_confirm),
                name='notifications_broadcastemail_send_confirm',
            ),
        ]
        return custom_urls + urls

    def send_confirm(self, request, pk):
        """Display a confirmation page before sending a broadcast."""
        broadcast = get_object_or_404(BroadcastEmail, pk=pk)

        # Check permission
        if not self.has_send_permission(request):
            raise PermissionDenied

        # Validate state
        if broadcast.status != 'DRAFT':
            messages.error(request, f"Broadcast '{broadcast.subject}' cannot be sent because its status is {broadcast.status}.")
            return HttpResponseRedirect(reverse('admin:notifications_broadcastemail_changelist'))

        if request.method == 'POST':
            # User confirmed – proceed with sending
            return self._send_broadcast(request, broadcast)

        # GET request – show confirmation template
        context = {
            **self.admin_site.each_context(request),
            'title': 'Confirm sending broadcast',
            'broadcast': broadcast,
            'recipient_count': broadcast.get_queryset().count(),  # rough estimate
            'opts': self.model._meta,
            'object': broadcast,
        }
        return render(request, 'admin/notifications/broadcastemail/send_confirm.html', context)

    def send_now(self, request, pk):
        """
        Legacy direct send URL – now redirects to confirmation.
        Maintained for backward compatibility (e.g., if old links are bookmarked).
        """
        broadcast = get_object_or_404(BroadcastEmail, pk=pk)
        return HttpResponseRedirect(reverse('admin:notifications_broadcastemail_send_confirm', args=[broadcast.pk]))

    @transaction.atomic
    def _send_broadcast(self, request, broadcast):
        """
        Core sending logic: mark as SENDING, enqueue task.
        Runs inside a transaction for consistency.
        """
        # Double‑check state (in case something changed since confirmation page)
        if broadcast.status != 'DRAFT':
            messages.error(request, f"Broadcast '{broadcast.subject}' cannot be sent because its status is {broadcast.status}.")
            return HttpResponseRedirect(reverse('admin:notifications_broadcastemail_changelist'))

        # Update status
        broadcast.status = 'SENDING'
        broadcast.save(update_fields=['status'])

        # Enqueue Celery task
        send_broadcast_email.delay(str(broadcast.id))

        messages.success(request, f"Broadcast '{broadcast.subject}' has been queued for sending.")
        logger.info(f"Broadcast {broadcast.id} queued by {request.user.email}")

        return HttpResponseRedirect(reverse('admin:notifications_broadcastemail_changelist'))


# ----- NEW ADMIN REGISTRATIONS (added without disrupting existing code) -----

@admin.register(BroadcastRecipient)
class BroadcastRecipientAdmin(admin.ModelAdmin):
    list_display = ['broadcast', 'user', 'status', 'sent_at']
    list_filter = ['status', 'broadcast']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'subject']
    fieldsets = (
        (None, {
            'fields': ('code', 'name', 'is_active')
        }),
        ('Content', {
            'fields': ('subject', 'plain_body', 'html_body')
        }),
        ('Metadata', {
            'fields': ('placeholders',)
        }),
    )