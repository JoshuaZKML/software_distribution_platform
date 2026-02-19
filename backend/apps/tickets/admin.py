from django.contrib import admin
from .models import Ticket, TicketMessage, TicketBan


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ('id', 'created_at')


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'subject', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'assigned_to')
    search_fields = ('subject', 'description', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'resolved_at', 'closed_at')
    inlines = [TicketMessageInline]


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('message', 'user__email')


@admin.register(TicketBan)
class TicketBanAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'reason', 'is_permanent', 'expires_at', 'created_at')
    list_filter = ('is_permanent', 'created_at')
    search_fields = ('user__email', 'reason')