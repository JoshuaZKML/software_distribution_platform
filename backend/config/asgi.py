"""
ASGI config for software distribution platform.
Exposes both HTTP and WebSocket (Channels) protocols.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

# Import WebSocket URL patterns from the central routing module
from backend.routing import websocket_urlpatterns

# ⚠️  NOTE: This default points to development settings.
#      In production, you MUST set the DJANGO_SETTINGS_MODULE environment variable
#      to the correct settings module (e.g., backend.config.settings.production).
#      The line below is kept exactly as in your original file to avoid disruption.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),          # Your original HTTP handling – unchanged
    "websocket": AllowedHostsOriginValidator(   # 🔐 Added origin validation (security)
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)    # 👈 Now using the imported patterns
        )
    ),
})