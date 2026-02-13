from django.urls import path
from backend.apps.notifications import consumers

websocket_urlpatterns = [
    path("ws/notifications/", consumers.NotificationConsumer.as_asgi()),
]