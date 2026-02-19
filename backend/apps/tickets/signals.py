import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Ticket, TicketMessage

# Use your actual notification service
from backend.apps.notifications.services import NotificationService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Ticket)
def ticket_post_save(sender, instance, created, **kwargs):
    if created:
        # Notify admins (optional – implement as needed)
        pass
    else:
        if hasattr(instance, '_original_status') and instance._original_status != instance.status:
            try:
                # Send in‑app notification to the ticket owner
                NotificationService.send(
                    user=instance.user,
                    channel='in_app',
                    subject=f"Ticket status updated: {instance.subject}",
                    body=f"Your ticket status changed from {instance._original_status} to {instance.status}.",
                    context={
                        'ticket_id': str(instance.id),
                        'subject': instance.subject,
                        'old_status': instance._original_status,
                        'new_status': instance.status,
                    }
                )
                # Also send email via Celery
                from .tasks import send_ticket_status_email
                try:
                    send_ticket_status_email.delay(instance.id, instance._original_status, instance.status)
                except Exception as e:
                    logger.exception("Failed to enqueue ticket status email")
            except Exception as e:
                logger.exception("Error in ticket status change notification")

        if (hasattr(instance, '_original_assigned') and
                instance._original_assigned != instance.assigned_to and
                instance.assigned_to):
            try:
                # Notify new assignee via in‑app notification
                NotificationService.send(
                    user=instance.assigned_to,
                    channel='in_app',
                    subject=f"Ticket assigned: {instance.subject}",
                    body=f"You have been assigned to ticket \"{instance.subject}\".",
                    context={
                        'ticket_id': str(instance.id),
                        'subject': instance.subject,
                        'assigned_by': instance._original_assigned.email if instance._original_assigned else 'System'
                    }
                )
                # Optionally send email to assignee as well
                # You can add a Celery task here if needed
            except Exception as e:
                logger.exception("Failed to notify assignee")


@receiver(post_save, sender=TicketMessage)
def ticket_message_post_save(sender, instance, created, **kwargs):
    if created:
        ticket = instance.ticket
        try:
            if instance.user == ticket.user:
                # User replied – notify assigned admin
                if ticket.assigned_to:
                    NotificationService.send(
                        user=ticket.assigned_to,
                        channel='in_app',
                        subject=f"New reply on ticket: {ticket.subject}",
                        body=f"{instance.user.email} replied: {instance.message[:100]}",
                        context={
                            'ticket_id': str(ticket.id),
                            'subject': ticket.subject,
                            'message': instance.message,
                            'user': ticket.user.email
                        }
                    )
            else:
                # Admin replied – notify user
                NotificationService.send(
                    user=ticket.user,
                    channel='in_app',
                    subject=f"New reply on your ticket: {ticket.subject}",
                    body=f"{instance.user.email} replied: {instance.message[:100]}",
                    context={
                        'ticket_id': str(ticket.id),
                        'subject': ticket.subject,
                        'message': instance.message,
                        'staff': instance.user.email
                    }
                )
                # Send email via Celery
                from .tasks import send_ticket_reply_email
                try:
                    send_ticket_reply_email.delay(instance.id)
                except Exception as e:
                    logger.exception("Failed to enqueue ticket reply email")
        except Exception as e:
            logger.exception("Error in ticket message notification")