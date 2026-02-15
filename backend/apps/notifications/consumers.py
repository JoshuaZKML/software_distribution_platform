# backend/apps/notifications/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real‑time notifications.
    - Authenticates the user (must be logged in and active).
    - Places the user in a personal group (user_<id>).
    - Forwards notification messages from the channel layer to the client.
    - Responds to client pings.
    """

    async def connect(self):
        """Accept connection only for authenticated, active users."""
        self.user = self.scope.get("user")

        # Reject unauthenticated or inactive users
        if not self.user or not self.user.is_authenticated or not self.user.is_active:
            logger.warning(
                "Unauthenticated or inactive WebSocket connection attempt: %s",
                getattr(self.user, "id", None)
            )
            await self.close(code=4001)
            return

        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"WebSocket connected for user {self.user.id}")

    async def disconnect(self, close_code):
        """Leave the user's group on disconnect."""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WebSocket disconnected for user {getattr(self, 'user', None)}")

    async def receive(self, text_data=None, bytes_data=None):
        """
        Handle incoming messages from the client.
        - Supports simple ping/pong for connection keep‑alive.
        - Malformed JSON is logged and ignored.
        """
        if text_data:
            try:
                data = json.loads(text_data)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from user {self.user.id}")
                return

            # Respond to ping with a pong
            if data.get("type") == "ping":
                await self.send_json({"type": "pong"})

        # Binary data is ignored (not used by this consumer)
        if bytes_data:
            logger.debug(f"Unexpected binary data from user {self.user.id}")

    async def notification_message(self, event):
        """
        Called when a message is sent to the user's group via the channel layer.
        event must contain a 'data' key with the notification payload.
        The payload is sent to the client exactly as provided (no extra wrapper)
        to maintain compatibility with the existing frontend code.
        """
        try:
            # Send the raw notification data (ensuring it's JSON serializable)
            await self.send_json(event["data"])
            logger.debug(f"Notification delivered to user {self.user.id}")
        except Exception as e:
            logger.error(f"Failed to send notification to user {self.user.id}: {e}")

    # Optional: Helper to send JSON responses consistently
    async def send_json(self, content):
        """Send a JSON‑serializable dict as a WebSocket text message."""
        await self.send(text_data=json.dumps(content))