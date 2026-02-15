# backend/apps/notifications/views.py
import logging

from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest  # added HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from rest_framework import generics, permissions
from rest_framework.response import Response

from .models import Notification, EmailTrackingEvent
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)

# 1×1 transparent GIF (used by track_open)
TRANSPARENT_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00'
    b'\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


# Tracking endpoints (public, no auth required)

@never_cache
@require_GET
@csrf_exempt  # because they are loaded via img src or link
def track_open(request, tracking_id):
    """
    Log an email open event and return a 1x1 transparent GIF.
    """
    try:
        notification = Notification.objects.get(tracking_id=tracking_id)
    except Notification.DoesNotExist:
        # Return empty GIF even if not found (to not leak info)
        return HttpResponse(TRANSPARENT_GIF, content_type='image/gif')

    # Log event
    EmailTrackingEvent.objects.create(
        notification=notification,
        broadcast=None,
        user=notification.user,
        email=notification.user.email if notification.user else '',
        event_type='open',
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        ip_address=_get_client_ip(request)
    )

    # Update notification opened_at if first open
    if not notification.opened_at:
        notification.opened_at = timezone.now()
        notification.save(update_fields=['opened_at'])

    return HttpResponse(TRANSPARENT_GIF, content_type='image/gif')


@never_cache
@require_GET
def track_click(request, tracking_id):
    """
    Log a click event and redirect to the original URL.
    The original URL is passed as a query parameter 'url'.
    """
    original_url = request.GET.get('url')
    if not original_url:
        return HttpResponseBadRequest("Missing url parameter")

    try:
        notification = Notification.objects.get(tracking_id=tracking_id)
    except Notification.DoesNotExist:
        # Redirect anyway, but don't log
        return HttpResponseRedirect(original_url)

    # Log click
    EmailTrackingEvent.objects.create(
        notification=notification,
        broadcast=None,
        user=notification.user,
        email=notification.user.email if notification.user else '',
        event_type='click',
        link_url=original_url,
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        ip_address=_get_client_ip(request)
    )

    # Update notification clicked_at if first click
    if not notification.clicked_at:
        notification.clicked_at = timezone.now()
        notification.clicked_url = original_url
        notification.save(update_fields=['clicked_at', 'clicked_url'])

    return HttpResponseRedirect(original_url)


def _get_client_ip(request):
    """Helper to extract client IP."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# In‑App Notification API (for users to fetch their notifications)

class NotificationListView(generics.ListAPIView):
    """List notifications for the authenticated user."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # During schema generation, avoid evaluating request.user
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')


class NotificationDetailView(generics.RetrieveAPIView):
    """Retrieve a single notification (and mark it as read? optionally)."""
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # During schema generation, avoid evaluating request.user
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user)