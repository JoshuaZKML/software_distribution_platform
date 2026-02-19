import logging
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Prefetch
from django.utils import timezone
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from backend.apps.accounts.permissions import IsAdmin
from backend.apps.accounts.models import AdminActionLog
from .models import ChatSession, ChatMessage, ChatBan
from .serializers import (
    ChatSessionSerializer, ChatSessionCreateSerializer,
    ChatMessageSerializer, ChatMessageCreateSerializer,
    ChatBanSerializer, ChatBanCreateSerializer
)
from .tasks import notify_admins_new_chat

User = get_user_model()
logger = logging.getLogger(__name__)


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


class ChatSessionViewSet(viewsets.ModelViewSet):
    queryset = ChatSession.objects.all().select_related('assigned_to')
    serializer_class = ChatSessionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'assigned_to']
    search_fields = ['visitor_name', 'visitor_email', 'visitor_phone']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if getattr(self, "swagger_fake_view", False):
            return ChatSession.objects.none()
        if user.is_authenticated and user.role in ['ADMIN', 'SUPER_ADMIN']:
            return super().get_queryset().prefetch_related(
                Prefetch(
                    'messages',
                    queryset=ChatMessage.objects.order_by('-created_at')[:1],
                    to_attr='last_msg'
                )
            )
        return ChatSession.objects.none()

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated, IsAdmin]
        return [p() for p in permission_classes]

    def create(self, request, *args, **kwargs):
        serializer = ChatSessionCreateSerializer(
            data=request.data,
            context={'request': request, 'ip_address': _get_client_ip(request)}
        )
        serializer.is_valid(raise_exception=True)

        session = ChatSession.objects.create(
            visitor_name=serializer.validated_data['name'],
            visitor_email=serializer.validated_data['email'],
            visitor_phone=serializer.validated_data['phone'],
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            status='pending'
        )

        # Compute queue position
        position = ChatSession.objects.filter(
            status='pending',
            created_at__lte=session.created_at
        ).count()

        # Broadcast to admins via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'admin_chat_notifications',
            {
                'type': 'new_chat_notification',
                'session_id': str(session.id),
                'visitor_name': session.visitor_name,
                'visitor_email': session.visitor_email,
                'created_at': session.created_at.isoformat(),
            }
        )

        # Optionally send Celery task for email/push (uncomment if needed)
        # notify_admins_new_chat.delay(str(session.id))

        return Response({
            'id': str(session.id),
            'visitor_token': session.visitor_token,
            'queue_position': position,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        session = self.get_object()
        if session.status != 'pending':
            return Response({'error': 'Session already assigned'}, status=status.HTTP_400_BAD_REQUEST)
        session.assigned_to = request.user
        session.status = 'active'
        session.save()
        return Response({'status': 'assigned'})

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        session = self.get_object()
        session.status = 'closed'
        session.closed_at = timezone.now()
        session.save()
        return Response({'status': 'closed'})

    @action(detail=True, methods=['post'], url_path='messages')
    def add_message(self, request, pk=None):
        session = self.get_object()
        serializer = ChatMessageCreateSerializer(
            data=request.data,
            context={'session': session, 'user': request.user}
        )
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        return Response(ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)


class ChatBanViewSet(viewsets.ModelViewSet):
    queryset = ChatBan.objects.all().select_related('created_by')
    serializer_class = ChatBanSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['email', 'ip_address', 'is_permanent']
    search_fields = ['reason', 'email']
    ordering_fields = ['created_at', 'expires_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return ChatBanCreateSerializer
        return ChatBanSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        try:
            AdminActionLog.objects.create(
                user=self.request.user,
                action_type='USER_BANNED_FROM_CHAT',
                target_id=str(instance.id),
                target_type='chatban',
                details={
                    'email': instance.email,
                    'ip': instance.ip_address,
                    'reason': instance.reason,
                    'is_permanent': instance.is_permanent,
                    'expires_at': instance.expires_at.isoformat() if instance.expires_at else None,
                },
                ip_address=_get_client_ip(self.request),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            )
        except Exception as e:
            logger.exception("Failed to log chat ban creation")

    def perform_destroy(self, instance):
        try:
            AdminActionLog.objects.create(
                user=self.request.user,
                action_type='USER_UNBANNED_FROM_CHAT',
                target_id=str(instance.id),
                target_type='chatban',
                details={'reason': 'Ban removed'},
                ip_address=_get_client_ip(self.request),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            )
        except Exception as e:
            logger.exception("Failed to log chat ban deletion")
        instance.delete()