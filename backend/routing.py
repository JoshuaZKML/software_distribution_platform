from django.urls import path, include
from backend.apps.notifications import consumers as notifications_consumers
from backend.apps.chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns

websocket_urlpatterns = [
    # Notifications WebSocket
    path("ws/notifications/", notifications_consumers.NotificationConsumer.as_asgi()),
    # Include all chat WebSocket patterns
    *chat_websocket_urlpatterns,
]