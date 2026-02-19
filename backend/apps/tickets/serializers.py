from rest_framework import serializers
from django.utils import timezone
from django.db.models import Q
from .models import Ticket, TicketMessage, TicketBan
from backend.apps.accounts.models import User


class TicketMessageSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    is_staff_reply = serializers.SerializerMethodField()

    class Meta:
        model = TicketMessage
        fields = [
            'id', 'ticket', 'user', 'user_email', 'is_staff_reply',
            'message', 'attachments', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']

    def get_is_staff_reply(self, obj):
        return obj.user.role in ['ADMIN', 'SUPER_ADMIN']


class TicketListSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, default=None)
    message_count = serializers.IntegerField(source='messages.count', read_only=True)
    last_message_at = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id', 'user', 'user_email', 'subject', 'status', 'priority',
            'assigned_to', 'assigned_to_email', 'created_at', 'updated_at',
            'message_count', 'last_message_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_last_message_at(self, obj):
        last = obj.messages.order_by('-created_at').first()
        return last.created_at if last else None


class TicketDetailSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, default=None)
    messages = TicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Ticket
        fields = '__all__'
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'resolved_at', 'closed_at']


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ['subject', 'description', 'priority']

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        if TicketBan.objects.filter(
            user=request.user
        ).filter(
            Q(is_permanent=True) | Q(expires_at__gt=timezone.now())
        ).exists():
            raise serializers.ValidationError("You are currently banned from creating tickets.")
        validated_data['user'] = request.user
        return super().create(validated_data)


class TicketUpdateSerializer(serializers.ModelSerializer):
    internal_note = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Ticket
        fields = ['status', 'priority', 'assigned_to', 'internal_note']

    def validate_status(self, value):
        return value

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


class TicketBanSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = TicketBan
        fields = [
            'id', 'user', 'user_email', 'reason', 'is_permanent', 'expires_at',
            'created_at', 'created_by', 'created_by_email', 'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'created_by']


class TicketBanCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketBan
        fields = ['user', 'reason', 'is_permanent', 'expires_at']

    def validate(self, data):
        if not data.get('is_permanent') and not data.get('expires_at'):
            raise serializers.ValidationError("Expiration date required for non‑permanent bans.")
        if data.get('expires_at') and data['expires_at'] <= timezone.now():
            raise serializers.ValidationError("Expiration date must be in the future.")
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        return super().create(validated_data)