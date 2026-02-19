import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberType
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Q
from django.core.cache import cache
from .models import ChatSession, ChatMessage, ChatBan


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_email = serializers.EmailField(source='sender.email', read_only=True, allow_null=True)
    is_admin = serializers.BooleanField(source='sender.role', read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'sender', 'sender_email', 'sender_name', 'content', 'created_at', 'is_admin']
        read_only_fields = ['id', 'created_at']


class ChatSessionSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    assigned_to_email = serializers.EmailField(source='assigned_to.email', read_only=True, default=None)

    class Meta:
        model = ChatSession
        fields = [
            'id', 'visitor_name', 'visitor_email', 'visitor_phone',
            'status', 'assigned_to', 'assigned_to_email',
            'created_at', 'updated_at', 'closed_at',
            'messages', 'last_message'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'closed_at']

    def get_last_message(self, obj):
        if hasattr(obj, 'last_msg') and obj.last_msg:
            return ChatMessageSerializer(obj.last_msg[0]).data
        return None


class ChatSessionCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=17)
    math_result = serializers.IntegerField(help_text="Result of the math question (e.g., 2+2=4)")

    def validate_email(self, value):
        return value.strip().lower()

    def validate_phone(self, value):
        request = self.context.get('request')
        country = request.data.get('country', 'NG') if request else 'NG'
        try:
            parsed = phonenumbers.parse(value, country)
        except NumberParseException:
            raise serializers.ValidationError("Invalid phone number format.")
        if not phonenumbers.is_valid_number(parsed):
            raise serializers.ValidationError("Phone number is not valid.")
        number_type = phonenumbers.number_type(parsed)
        if number_type not in (PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE):
            raise serializers.ValidationError("Only mobile numbers are allowed.")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    def validate(self, data):
        if data.get('math_result') != 4:
            raise serializers.ValidationError("Incorrect math result. Please try again.")
        ip = self.context.get('ip_address')
        now = timezone.now()
        if ChatBan.objects.filter(
            (Q(email=data['email']) | Q(ip_address=ip))
        ).filter(
            Q(is_permanent=True) | Q(expires_at__gt=now)
        ).exists():
            raise serializers.ValidationError("You are banned from starting a chat.")
        rate_key = f"chat_create_rate:{ip}"
        current = cache.get(rate_key, 0)
        if current >= 5:
            raise serializers.ValidationError("Too many chat attempts. Please try later.")
        cache.set(rate_key, current + 1, timeout=60)
        return data


class ChatMessageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['content']

    def create(self, validated_data):
        session = self.context['session']
        user = self.context.get('user')
        if user and user.is_authenticated:
            return ChatMessage.objects.create(
                session=session,
                sender=user,
                content=validated_data['content']
            )
        else:
            return ChatMessage.objects.create(
                session=session,
                sender_name=session.visitor_name,
                content=validated_data['content']
            )


class ChatBanSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = ChatBan
        fields = [
            'id', 'email', 'ip_address', 'reason',
            'is_permanent', 'expires_at', 'created_at',
            'created_by', 'created_by_email', 'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'created_by']


class ChatBanCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatBan
        fields = ['email', 'ip_address', 'reason', 'is_permanent', 'expires_at']

    def validate(self, data):
        if not data.get('email') and not data.get('ip_address'):
            raise serializers.ValidationError("Either email or IP address must be provided.")
        if not data.get('is_permanent') and not data.get('expires_at'):
            raise serializers.ValidationError("Expiration date required for non‑permanent bans.")
        if data.get('expires_at') and data['expires_at'] <= timezone.now():
            raise serializers.ValidationError("Expiration date must be in the future.")
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        return super().create(validated_data)