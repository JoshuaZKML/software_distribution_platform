import logging
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from backend.apps.accounts.permissions import IsAdmin
from backend.apps.accounts.models import AdminActionLog  # <-- NEW import
from .models import Ticket, TicketMessage, TicketBan
from .serializers import (
    TicketListSerializer, TicketDetailSerializer, TicketCreateSerializer,
    TicketUpdateSerializer, TicketMessageSerializer, TicketBanSerializer,
    TicketBanCreateSerializer
)
from .permissions import IsTicketOwnerOrAdmin, NotBannedFromTickets

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    """Extract client IP from request (copied from accounts.views)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all().select_related(
        'user', 'assigned_to'
    ).prefetch_related('messages')
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'priority', 'assigned_to']
    search_fields = ['subject', 'description', 'user__email']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if getattr(self, "swagger_fake_view", False):
            return Ticket.objects.none()
        if user.role in ['ADMIN', 'SUPER_ADMIN']:
            return super().get_queryset()
        return super().get_queryset().filter(user=user)

    def get_serializer_class(self):
        if self.action == 'list':
            return TicketListSerializer
        elif self.action == 'retrieve':
            return TicketDetailSerializer
        elif self.action == 'create':
            return TicketCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TicketUpdateSerializer
        return TicketDetailSerializer

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated, NotBannedFromTickets]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated, IsTicketOwnerOrAdmin]
        return [p() for p in permission_classes]

    def perform_create(self, serializer):
        """Create ticket and log action."""
        ticket = serializer.save()
        try:
            AdminActionLog.objects.create(
                user=self.request.user,
                action_type='TICKET_CREATED',
                target_id=str(ticket.id),
                target_type='ticket',
                details={
                    'subject': ticket.subject,
                    'priority': ticket.priority,
                },
                ip_address=_get_client_ip(self.request),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            )
        except Exception as e:
            logger.exception("Failed to log ticket creation")

    def perform_update(self, serializer):
        """Update ticket and log changes."""
        old_instance = self.get_object()
        old_status = old_instance.status
        old_assigned = old_instance.assigned_to_id
        new_instance = serializer.save()
        changes = {}
        if old_status != new_instance.status:
            changes['status'] = {'old': old_status, 'new': new_instance.status}
        if old_assigned != new_instance.assigned_to_id:
            changes['assigned_to'] = {
                'old': str(old_assigned) if old_assigned else None,
                'new': str(new_instance.assigned_to_id) if new_instance.assigned_to_id else None
            }
        # Only log if something changed (optional)
        if changes:
            try:
                AdminActionLog.objects.create(
                    user=self.request.user,
                    action_type='TICKET_UPDATED',
                    target_id=str(new_instance.id),
                    target_type='ticket',
                    details=changes,
                    ip_address=_get_client_ip(self.request),
                    user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
                )
            except Exception as e:
                logger.exception("Failed to log ticket update")

    def perform_destroy(self, instance):
        """Delete ticket and log action."""
        ticket_id = str(instance.id)
        subject = instance.subject
        instance.delete()
        try:
            AdminActionLog.objects.create(
                user=self.request.user,
                action_type='SOFTWARE_DELETED',  # Reuse existing or create TICKET_DELETED if needed
                target_id=ticket_id,
                target_type='ticket',
                details={'subject': subject},
                ip_address=_get_client_ip(self.request),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            )
        except Exception as e:
            logger.exception("Failed to log ticket deletion")

    @action(detail=True, methods=['post'], url_path='messages')
    def add_message(self, request, pk=None):
        ticket = self.get_object()
        serializer = TicketMessageSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        message = serializer.save(ticket=ticket, user=request.user)
        # Log the message addition
        try:
            AdminActionLog.objects.create(
                user=request.user,
                action_type='TICKET_MESSAGE_ADDED',
                target_id=str(ticket.id),
                target_type='ticket',
                details={
                    'message_preview': message.message[:100],
                    'is_staff': request.user.role in ['ADMIN', 'SUPER_ADMIN']
                },
                ip_address=_get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        except Exception as e:
            logger.exception("Failed to log ticket message")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='messages')
    def list_messages(self, request, pk=None):
        ticket = self.get_object()
        messages = ticket.messages.all()
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = TicketMessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = TicketMessageSerializer(messages, many=True)
        return Response(serializer.data)


class TicketBanViewSet(viewsets.ModelViewSet):
    queryset = TicketBan.objects.all().select_related('user', 'created_by')
    serializer_class = TicketBanSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'is_permanent']
    search_fields = ['reason', 'user__email']
    ordering_fields = ['created_at', 'expires_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return TicketBanCreateSerializer
        return TicketBanSerializer

    def perform_create(self, serializer):
        """Create ban and log action."""
        instance = serializer.save()
        try:
            AdminActionLog.objects.create(
                user=self.request.user,
                action_type='USER_BANNED_FROM_TICKETS',
                target_id=str(instance.user.id),
                target_type='user',
                details={
                    'reason': instance.reason,
                    'is_permanent': instance.is_permanent,
                    'expires_at': instance.expires_at.isoformat() if instance.expires_at else None,
                },
                ip_address=_get_client_ip(self.request),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            )
        except Exception as e:
            logger.exception("Failed to log ticket ban creation")

    def perform_destroy(self, instance):
        """Delete ban and log action."""
        user_id = str(instance.user.id)
        reason = instance.reason
        instance.delete()
        try:
            AdminActionLog.objects.create(
                user=self.request.user,
                action_type='USER_UNBANNED_FROM_TICKETS',
                target_id=user_id,
                target_type='user',
                details={'reason': reason},
                ip_address=_get_client_ip(self.request),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            )
        except Exception as e:
            logger.exception("Failed to log ticket ban deletion")