from django.contrib import admin
from .models import ChatSession, ChatMessage, ChatBan


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('id', 'created_at')


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'visitor_name', 'visitor_email', 'status', 'assigned_to', 'created_at')
    list_filter = ('status', 'assigned_to')
    search_fields = ('visitor_name', 'visitor_email', 'visitor_phone')
    readonly_fields = ('id', 'visitor_token', 'created_at', 'updated_at', 'closed_at')
    inlines = [ChatMessageInline]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'sender', 'sender_name', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('content',)


@admin.register(ChatBan)
class ChatBanAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'ip_address', 'reason', 'is_permanent', 'expires_at', 'created_at')
    list_filter = ('is_permanent', 'created_at')
    search_fields = ('email', 'reason')