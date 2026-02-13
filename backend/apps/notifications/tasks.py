# backend/apps/notifications/tasks.py
import math
import logging
import uuid  # added for new notification tasks
from celery import shared_task
from django.db import models, transaction
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from django.urls import reverse  # added for new notification tasks
from django.template.loader import render_to_string  # added
from django.utils.html import strip_tags  # added
from urllib.parse import quote  # added (used inside helper function)
from .models import BroadcastEmail, Notification, EmailTrackingEvent  # added Notification and EmailTrackingEvent
from .utils import render_template  # added (assumes this utility exists)

logger = logging.getLogger(__name__)

BATCH_SIZE = 50  # Emails per batch – adjust based on your SMTP limits


@shared_task
def send_broadcast_email(broadcast_id):
    """
    Orchestrate sending of a broadcast email.
    Uses select_for_update to prevent duplicate sends.
    Creates batch tasks and tracks progress via total_batches/completed_batches.
    """
    with transaction.atomic():
        # Lock the broadcast row to prevent concurrent sends
        broadcast = BroadcastEmail.objects.select_for_update().get(id=broadcast_id)

        # If already sending or sent, abort
        if broadcast.status not in ['DRAFT', 'SENDING']:
            logger.warning(f"Broadcast {broadcast_id} is {broadcast.status}, not sending.")
            return

        # If scheduled for future, reschedule using Celery ETA
        if broadcast.scheduled_at and broadcast.scheduled_at > timezone.now():
            send_broadcast_email.apply_async(
                args=[broadcast_id],
                eta=broadcast.scheduled_at
            )
            logger.info(f"Broadcast {broadcast_id} scheduled for {broadcast.scheduled_at}")
            return

        # Transition to SENDING (if not already)
        if broadcast.status == 'DRAFT':
            broadcast.status = 'SENDING'
            broadcast.save(update_fields=['status'])

    # Get recipient queryset (already filtered by audience and unsubscribed)
    qs = broadcast.get_queryset()
    if hasattr(qs, 'exclude'):
        qs = qs.exclude(unsubscribed=True)  # ensure unsubscribed are excluded

    # Count total recipients efficiently
    total_recipients = qs.count()
    if total_recipients == 0:
        logger.info(f"Broadcast {broadcast_id} has no recipients, marking as sent.")
        with transaction.atomic():
            broadcast = BroadcastEmail.objects.select_for_update().get(id=broadcast_id)
            broadcast.status = 'SENT'
            broadcast.sent_at = timezone.now()
            broadcast.total_recipients = 0
            broadcast.save(update_fields=['status', 'sent_at', 'total_recipients'])
        return

    # Calculate number of batches
    total_batches = math.ceil(total_recipients / BATCH_SIZE)

    # Update broadcast with recipient count and batch info (atomic update)
    BroadcastEmail.objects.filter(id=broadcast_id).update(
        total_recipients=total_recipients,
        total_batches=total_batches,
        completed_batches=0,
    )

    # Enqueue batch tasks – stream recipients in chunks to avoid memory blow
    email_iterator = qs.values_list('email', flat=True).iterator(chunk_size=BATCH_SIZE)
    batch_number = 0
    batch_emails = []

    for email in email_iterator:
        batch_emails.append(email)
        if len(batch_emails) == BATCH_SIZE:
            send_broadcast_batch.delay(broadcast_id, batch_emails, batch_number, total_batches)
            batch_emails = []
            batch_number += 1

    # Send the last partial batch if any
    if batch_emails:
        send_broadcast_batch.delay(broadcast_id, batch_emails, batch_number, total_batches)

    logger.info(f"Broadcast {broadcast_id}: {total_recipients} recipients, {total_batches} batches enqueued.")


@shared_task(rate_limit='10/m')  # max 10 batches per minute – adjust to your SMTP limits
def send_broadcast_batch(broadcast_id, email_batch, batch_number, total_batches):
    """
    Send one batch of emails.
    Updates success/failure counts and tracks batch completion.
    Marks broadcast as SENT when all batches are done.
    """
    from backend.apps.accounts.models import User

    # Re-filter unsubscribed users (safety net)
    subscribed_emails = list(
        User.objects.filter(email__in=email_batch, unsubscribed=False)
        .values_list('email', flat=True)
    )

    success_count = 0
    failure_count = 0

    for email in subscribed_emails:
        try:
            msg = EmailMultiAlternatives(
                subject=broadcast.subject,
                body=broadcast.plain_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )
            msg.attach_alternative(broadcast.html_body, "text/html")
            msg.send(fail_silently=False)
            success_count += 1
        except Exception as e:
            failure_count += 1
            logger.error(f"Failed to send broadcast {broadcast_id} to {email}: {e}")

    # Atomically update broadcast counts and completed batches
    with transaction.atomic():
        broadcast = BroadcastEmail.objects.select_for_update().get(id=broadcast_id)

        # Update success/failure counts
        broadcast.successful_sent += success_count
        broadcast.failed_sent += failure_count

        # Increment completed batches
        broadcast.completed_batches += 1
        broadcast.save(update_fields=['successful_sent', 'failed_sent', 'completed_batches'])

        # If all batches are done, mark as SENT
        if broadcast.completed_batches >= broadcast.total_batches:
            broadcast.status = 'SENT'
            broadcast.sent_at = timezone.now()
            broadcast.save(update_fields=['status', 'sent_at'])
            logger.info(f"Broadcast {broadcast_id} fully sent.")

    logger.debug(f"Batch {batch_number+1}/{total_batches} for broadcast {broadcast_id} completed. "
                 f"Success: {success_count}, Failed: {failure_count}")


# =============================================================================
# New tasks for centralised notification service (added without disruption)
# =============================================================================

def _get_tracking_pixel_url(notification_id, tracking_id):
    """Generate absolute URL for tracking pixel."""
    # Assumes you have a setting SITE_URL or you can build from request; here we use a setting.
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    return f"{site_url}/api/notifications/track/open/{tracking_id}/"


def _get_tracking_click_url(notification_id, tracking_id, original_url):
    """Generate tracking redirect URL for a click."""
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    # URL encode original_url
    from urllib.parse import quote
    return f"{site_url}/api/notifications/track/click/{tracking_id}/?url={quote(original_url)}"


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_email_notification(self, notification_id):
    """Send an email notification (renders template if needed)."""
    try:
        notification = Notification.objects.select_related('user', 'template').get(id=notification_id)
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found.")
        return

    if notification.status != 'pending':
        logger.warning(f"Notification {notification_id} already {notification.status}, skipping.")
        return

    user = notification.user
    if not user or not user.email:
        logger.warning(f"Notification {notification_id}: user or email missing, marking failed.")
        notification.status = 'failed'
        notification.error_message = "User or email missing"
        notification.save()
        return

    # Render subject/body from template if needed
    subject = notification.subject
    plain_body = notification.body
    html_body = notification.html_body

    if notification.template:
        # Render using template and context
        context = notification.context
        # Add standard context items
        context.update({
            'user': user,
            'unsubscribe_url': user.get_unsubscribe_token_url()  # you may need to define this helper
        })
        rendered = render_template(notification.template.code, context, raise_if_missing=False)
        if rendered[0] is None:
            notification.status = 'failed'
            notification.error_message = f"Template '{notification.template.code}' missing or inactive"
            notification.save()
            return
        subject, plain_body, html_body = rendered

    # Inject tracking pixel and link wrapping
    tracking_id = notification.tracking_id
    if tracking_id:
        # Add tracking pixel to HTML
        pixel_url = _get_tracking_pixel_url(notification_id, tracking_id)
        pixel_html = f'<img src="{pixel_url}" width="1" height="1" style="display:none;" alt=""/>'
        if html_body:
            html_body += pixel_html
        else:
            html_body = plain_body + pixel_html

        # Wrap any links we want to track (e.g., all links, or specific ones)
        # For simplicity, we can replace all hrefs with tracking redirects.
        # This is complex; for now we'll just note that it requires parsing HTML.
        # Alternatively, we can provide a utility to rewrite links.
        # We'll implement a basic link wrapper that replaces absolute URLs in HTML.
        # (Implementation omitted for brevity but can be added later.)
        pass

    # Prepare email
    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        reply_to=[settings.SUPPORT_EMAIL],
    )
    if html_body:
        email.attach_alternative(html_body, "text/html")

    try:
        email.send(fail_silently=False)
        notification.status = 'sent'
        notification.sent_at = timezone.now()
        notification.save()
        logger.info(f"Email notification {notification_id} sent to {user.email}")
    except Exception as e:
        logger.exception(f"Failed to send email notification {notification_id}")
        notification.status = 'failed'
        notification.error_message = str(e)
        notification.save()
        raise  # trigger retry


@shared_task
def send_in_app_notification(notification_id):
    """Create an in‑app notification record (for future expansion)."""
    try:
        notification = Notification.objects.get(id=notification_id)
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found.")
        return

    if notification.status != 'pending':
        return

    # For now, in‑app just marks as sent (no actual delivery)
    notification.status = 'sent'
    notification.sent_at = timezone.now()
    notification.save()
    logger.info(f"In‑app notification {notification_id} marked as sent.")