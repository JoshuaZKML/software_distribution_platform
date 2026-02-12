# FILE: /backend/apps/licenses/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    ActivationCode,
    ActivationLog,
    LicenseFeature,
    CodeBatch,
    LicenseUsage,
    RevocationLog,
)


@admin.register(LicenseFeature)
class LicenseFeatureAdmin(admin.ModelAdmin):
    """
    Admin interface for license features.
    Uses individual boolean fields for license tier availability.
    """
    list_display = ('name', 'code', 'software', 'is_active', 'display_order')
    list_filter = ('software', 'is_active')
    search_fields = ('name', 'code', 'description', 'software__name')

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'software', 'description')
        }),
        ('Status & Display', {
            'fields': ('is_active', 'display_order', 'requires_activation', 'max_usage')
        }),
        ('License Tier Availability', {
            'fields': (
                'available_in_trial',
                'available_in_standard',
                'available_in_premium',
                'available_in_enterprise'
            ),
            'description': 'Select which license types can access this feature.'
        }),
    )


@admin.register(CodeBatch)
class CodeBatchAdmin(admin.ModelAdmin):
    """
    Admin interface for code batches.
    Shows real‑time utilization and links to generated codes.
    """
    list_display = ('name', 'software', 'license_type', 'count', 'utilization', 'created_at')
    list_filter = ('software', 'license_type', 'is_used')
    search_fields = ('name', 'description', 'software__name')
    readonly_fields = ('used_count', 'unused_count', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'software', 'description', 'license_type')
        }),
        ('Generation Settings', {
            'fields': ('count', 'max_activations', 'expires_in_days', 'prefix')
        }),
        ('Status', {
            'fields': ('is_used', 'used_count', 'unused_count', 'generated_by', 'created_at')
        }),
    )

    def utilization(self, obj):
        """Visual indicator of batch usage."""
        if obj.count == 0:
            return "0%"
        percent = (obj.used_count / obj.count) * 100
        color = 'green' if percent < 80 else 'orange' if percent < 100 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} / {} ({:.1f}%)</span>',
            color, obj.used_count, obj.count, percent
        )
    utilization.short_description = 'Utilization'


@admin.register(ActivationCode)
class ActivationCodeAdmin(admin.ModelAdmin):
    """
    Admin interface for activation codes / licenses.
    Provides quick overview of ownership, status, and device binding.
    """
    list_display = (
        'human_code_short',
        'software',
        'user_email',
        'license_type',
        'status_badge',
        'expires_at',
        'activation_count',
        'created_at'
    )
    list_filter = (
        'status',
        'license_type',
        'software',
        'expires_at',
    )
    search_fields = (
        'human_code',
        'user__email',
        'device_fingerprint',
        'notes'
    )
    readonly_fields = (
        'human_code',
        'code_hash',
        'encrypted_code',
        'created_at',
        'activated_at',
        'revoked_at',
        'last_used_at',
        'updated_at',
        'remaining_activations',
        'days_until_expiry',
    )
    fieldsets = (
        ('Activation Code', {
            'fields': ('human_code', 'software', 'software_version', 'license_type', 'status')
        }),
        ('Ownership', {
            'fields': ('user', 'generated_by')
        }),
        ('Activation Limits', {
            'fields': ('max_activations', 'activation_count', 'concurrent_limit', 'remaining_activations')
        }),
        ('Device Binding', {
            'fields': ('device_fingerprint', 'device_name', 'device_info')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'activated_at', 'expires_at', 'last_used_at', 'updated_at')
        }),
        ('Revocation', {
            'fields': ('revoked_at', 'revoked_by', 'revoked_reason'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('batch', 'notes', 'custom_data'),
            'classes': ('collapse',)
        }),
    )

    def human_code_short(self, obj):
        """Display truncated activation code."""
        code = obj.human_code
        if len(code) > 16:
            return f"{code[:8]}…{code[-8:]}"
        return code
    human_code_short.short_description = 'Activation Code'
    human_code_short.admin_order_field = 'human_code'

    def user_email(self, obj):
        return obj.user.email if obj.user else None
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def status_badge(self, obj):
        """Color‑coded status badge."""
        colors = {
            'GENERATED': 'gray',
            'ACTIVATED': 'green',
            'EXPIRED': 'orange',
            'REVOKED': 'red',
            'SUSPENDED': 'purple',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    actions = ['revoke_selected', 'export_selected']

    def revoke_selected(self, request, queryset):
        """Bulk revoke activation codes."""
        revoked = 0
        for code in queryset:
            if code.revoke(revoked_by=request.user, reason="Bulk revocation via admin"):
                revoked += 1
        self.message_user(request, f'Successfully revoked {revoked} activation codes.')
    revoke_selected.short_description = "Revoke selected codes"

    def export_selected(self, request, queryset):
        """Export selected codes as CSV."""
        import csv
        from django.http import HttpResponse
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Code', 'Software', 'License Type', 'Status', 'User', 'Expires At', 'Max Activations', 'Activation Count'])
        for code in queryset:
            writer.writerow([
                code.human_code,
                code.software.name,
                code.license_type,
                code.status,
                code.user.email if code.user else '',
                code.expires_at.isoformat() if code.expires_at else '',
                code.max_activations,
                code.activation_count,
            ])
        output.seek(0)
        response = HttpResponse(output, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="activation_codes.csv"'
        return response
    export_selected.short_description = "Export selected codes to CSV"


@admin.register(ActivationLog)
class ActivationLogAdmin(admin.ModelAdmin):
    """
    Admin interface for activation attempts.
    Critical for abuse detection and audit trails.
    """
    list_display = (
        'activation_code_link',
        'action',
        'success_badge',
        'ip_address',
        'device_fingerprint_short',
        'created_at'
    )
    list_filter = ('action', 'success', 'is_suspicious', 'created_at')
    search_fields = (
        'activation_code__human_code',
        'device_fingerprint',
        'ip_address',
        'user_agent'
    )
    readonly_fields = (
        'activation_code',
        'device_fingerprint',
        'device_name',
        'device_info',
        'ip_address',
        'user_agent',
        'location',
        'action',
        'success',
        'error_message',
        'is_suspicious',
        'suspicion_reason',
        'created_at'
    )
    list_select_related = ('activation_code',)

    def activation_code_link(self, obj):
        """Link to the related activation code in admin."""
        url = reverse('admin:licenses_activationcode_change', args=[obj.activation_code.id])
        return format_html('<a href="{}">{}</a>', url, obj.activation_code.human_code)
    activation_code_link.short_description = 'Activation Code'
    activation_code_link.admin_order_field = 'activation_code__human_code'

    def success_badge(self, obj):
        """Color‑coded success indicator."""
        color = 'green' if obj.success else 'red'
        text = 'Success' if obj.success else 'Failed'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, text
        )
    success_badge.short_description = 'Outcome'
    success_badge.admin_order_field = 'success'

    def device_fingerprint_short(self, obj):
        if obj.device_fingerprint and len(obj.device_fingerprint) > 12:
            return f"{obj.device_fingerprint[:8]}…"
        return obj.device_fingerprint or ''
    device_fingerprint_short.short_description = 'Device FP'


@admin.register(LicenseUsage)
class LicenseUsageAdmin(admin.ModelAdmin):
    """
    Admin interface for feature usage tracking.
    Correlates directly with LicenseUsageViewSet.log_usage.
    """
    list_display = (
        'activation_code_link',
        'feature_name',
        'usage_count',
        'device_fingerprint_short',
        'created_at'
    )
    list_filter = ('feature', 'created_at')
    search_fields = (
        'activation_code__human_code',
        'feature__name',
        'feature__code',
        'device_fingerprint'
    )
    readonly_fields = (
        'activation_code',
        'feature',
        'usage_count',
        'usage_data',
        'device_fingerprint',
        'ip_address',
        'created_at',
        'updated_at'
    )

    def activation_code_link(self, obj):
        url = reverse('admin:licenses_activationcode_change', args=[obj.activation_code.id])
        return format_html('<a href="{}">{}</a>', url, obj.activation_code.human_code)
    activation_code_link.short_description = 'Activation Code'

    def feature_name(self, obj):
        return obj.feature.name if obj.feature else '-'
    feature_name.short_description = 'Feature'

    def device_fingerprint_short(self, obj):
        if obj.device_fingerprint and len(obj.device_fingerprint) > 12:
            return f"{obj.device_fingerprint[:8]}…"
        return obj.device_fingerprint or ''
    device_fingerprint_short.short_description = 'Device FP'


@admin.register(RevocationLog)
class RevocationLogAdmin(admin.ModelAdmin):
    """
    Admin interface for revocation audit trail.
    Supports undo tracking.
    """
    list_display = (
        'activation_code_link',
        'revoked_by_email',
        'reason_short',
        'undone_badge',
        'created_at'
    )
    list_filter = ('undone', 'created_at')
    search_fields = (
        'activation_code__human_code',
        'revoked_by__email',
        'reason'
    )
    readonly_fields = (
        'activation_code',
        'revoked_by',
        'reason',
        'details',
        'undone',
        'undone_by',
        'undone_at',
        'undo_reason',
        'created_at'
    )

    def activation_code_link(self, obj):
        url = reverse('admin:licenses_activationcode_change', args=[obj.activation_code.id])
        return format_html('<a href="{}">{}</a>', url, obj.activation_code.human_code)
    activation_code_link.short_description = 'Activation Code'

    def revoked_by_email(self, obj):
        return obj.revoked_by.email if obj.revoked_by else '-'
    revoked_by_email.short_description = 'Revoked By'
    revoked_by_email.admin_order_field = 'revoked_by__email'

    def reason_short(self, obj):
        if len(obj.reason) > 50:
            return f"{obj.reason[:50]}…"
        return obj.reason
    reason_short.short_description = 'Reason'

    def undone_badge(self, obj):
        if obj.undone:
            return format_html(
                '<span style="color: gray;">✓ Undone by {}</span>',
                obj.undone_by.email if obj.undone_by else 'unknown'
            )
        return format_html('<span style="color: red;">✗ Active</span>')
    undone_badge.short_description = 'Status'