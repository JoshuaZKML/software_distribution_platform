import json
import logging
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.db import models
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from .models import ChatSession, ChatMessage, ChatBan

User = get_user_model()
logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'chat_{self.session_id}'

        self.user = await self.get_user_from_scope()
        self.is_admin = self.user and not isinstance(self.user, AnonymousUser)

        self.session = await self.get_session(self.session_id)
        if not self.session:
            logger.warning(f"Chat session {self.session_id} not found")
            await self.close()
            return

        if not self.is_admin:
            visitor_email = self.get_query_param('email')
            visitor_token = self.get_query_param('token')
            ip = self.get_client_ip()
            if (self.session.visitor_email != visitor_email or
                    self.session.visitor_token != visitor_token or
                    self.session.ip_address != ip):
                logger.warning(f"Visitor mismatch for session {self.session_id}")
                await self.close()
                return
            if await self.is_banned(self.session.visitor_email, ip):
                await self.close()
                return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # If admin connects and session is pending, mark active and notify visitor
        if self.is_admin and self.session.status == 'pending':
            await self.mark_session_active(self.session_id, self.user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'chat_active', 'message': 'An admin has joined the chat.'}
            )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type', 'message')

        if msg_type == 'message':
            content = data.get('content', '').strip()
            if not content or len(content) > 5000:
                await self.send(json.dumps({'type': 'error', 'message': 'Invalid message'}))
                return
            message = await self.save_message(self.session, content, self.user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'id': str(message.id),
                    'sender_id': str(self.user.id) if self.user else None,
                    'sender_name': message.sender_name,
                    'content': message.content,
                    'created_at': message.created_at.isoformat(),
                    'is_admin': self.is_admin,
                }
            )
        elif msg_type == 'close' and self.is_admin:
            await self.close_session(self.session_id)
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'chat_closed'}
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def chat_active(self, event):
        await self.send(text_data=json.dumps({'type': 'active', 'message': event['message']}))

    async def chat_closed(self, event):
        await self.send(text_data=json.dumps({'type': 'closed'}))
        await self.close()

    # Database helpers
    @database_sync_to_async
    def get_user_from_scope(self):
        query_string = self.scope['query_string'].decode()
        params = parse_qs(query_string)
        token_list = params.get('token', [])
        token = token_list[0] if token_list else None
        if not token:
            return AnonymousUser()
        try:
            access_token = AccessToken(token)
            user = User.objects.get(id=access_token['user_id'])
            return user
        except Exception:
            return AnonymousUser()

    def get_query_param(self, key):
        query_string = self.scope['query_string'].decode()
        params = parse_qs(query_string)
        return params.get(key, [None])[0]

    def get_client_ip(self):
        headers = dict(self.scope['headers'])
        x_forwarded_for = headers.get(b'x-forwarded-for', b'').decode()
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return self.scope.get('client', ('', 0))[0]

    @database_sync_to_async
    def get_session(self, session_id):
        try:
            return ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return None

    @database_sync_to_async
    def is_banned(self, email, ip):
        now = timezone.now()
        return ChatBan.objects.filter(
            (models.Q(email=email) | models.Q(ip_address=ip))
        ).filter(
            models.Q(is_permanent=True) | models.Q(expires_at__gt=now)
        ).exists()

    @database_sync_to_async
    def mark_session_active(self, session_id, admin):
        ChatSession.objects.filter(id=session_id, status='pending').update(
            status='active',
            assigned_to=admin,
            updated_at=timezone.now()
        )

    @database_sync_to_async
    def save_message(self, session, content, user):
        if user and not isinstance(user, AnonymousUser):
            return ChatMessage.objects.create(
                session=session,
                sender=user,
                content=content
            )
        else:
            return ChatMessage.objects.create(
                session=session,
                sender_name=session.visitor_name,
                content=content
            )

    @database_sync_to_async
    def close_session(self, session_id):
        ChatSession.objects.filter(id=session_id).update(
            status='closed',
            closed_at=timezone.now()
        )


class AdminChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = await self.get_user_from_scope()
        if not self.user or isinstance(self.user, AnonymousUser) or self.user.role not in ['ADMIN', 'SUPER_ADMIN']:
            await self.close()
            return

        self.group_name = 'admin_chat_notifications'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def new_chat_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_chat',
            'session_id': event['session_id'],
            'visitor_name': event['visitor_name'],
            'visitor_email': event['visitor_email'],
            'created_at': event['created_at'],
        }))

    @database_sync_to_async
    def get_user_from_scope(self):
        from urllib.parse import parse_qs
        query_string = self.scope['query_string'].decode()
        params = parse_qs(query_string)
        token_list = params.get('token', [])
        token = token_list[0] if token_list else None
        if not token:
            return AnonymousUser()
        try:
            access_token = AccessToken(token)
            user = User.objects.get(id=access_token['user_id'])
            return user
        except Exception:
            return AnonymousUser()