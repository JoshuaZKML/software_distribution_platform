# FILE: backend/apps/notifications/services.py
import uuid
import logging
from django.conf import settings
from django.utils import timezone
from .models import Notification, EmailTemplate
from .tasks import send_email_notification, send_in_app_notification

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Unified interface for sending notifications across channels.
    Usage:
        NotificationService.send(user, 'email', template_code='welcome', context={'name': user.first_name})
        NotificationService.send(user, 'in_app', body='Hello')
    """

    @classmethod
    def send(cls, user, channel, template_code=None, context=None, subject=None, body=None, html_body=None):
        """
        Create a Notification record and enqueue the appropriate Celery task.
        At least one of (template_code) or (subject+body) must be provided.
        """
        if not user or not user.email:
            logger.warning(f"Cannot send notification to user {user}: missing user or email.")
            return None

        # Validate arguments
        if template_code:
            # Template will be rendered later (by the task)
            pass
        elif subject and body:
            # Use provided strings directly
            pass
        else:
            raise ValueError("Either template_code or subject+body must be provided.")

        # Create notification record
        notification = Notification.objects.create(
            user=user,
            channel=channel,
            template_id=EmailTemplate.objects.filter(code=template_code).values_list('id', flat=True).first() if template_code else None,
            subject=subject or '',
            body=body or '',
            html_body=html_body or '',
            context=context or {},
            tracking_id=uuid.uuid4(),  # generate a tracking ID for open/click tracking
            status='pending'
        )

        # Enqueue appropriate task
        if channel == 'email':
            send_email_notification.delay(str(notification.id))
        elif channel == 'in_app':
            send_in_app_notification.delay(str(notification.id))
        else:
            logger.error(f"Unsupported channel: {channel}")
            notification.status = 'failed'
            notification.error_message = f"Unsupported channel: {channel}"
            notification.save()

        logger.info(f"Notification {notification.id} created and queued for {user.email} via {channel}")
        return notification