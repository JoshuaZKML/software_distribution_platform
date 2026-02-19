# backend/apps/tickets/tasks.py
import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Ticket, TicketMessage

logger = logging.getLogger(__name__)


@shared_task
def send_ticket_status_email(ticket_id, old_status, new_status):
    try:
        ticket = Ticket.objects.select_related('user').get(id=ticket_id)
    except Ticket.DoesNotExist:
        logger.warning(f"Ticket {ticket_id} not found for status email")
        return

    subject = f"Ticket #{ticket.id} status updated"
    message = f"""
    Hello {ticket.user.get_full_name() or ticket.user.email},

    The status of your ticket "{ticket.subject}" has changed from {old_status} to {new_status}.

    You can view the ticket at: {settings.FRONTEND_URL}/tickets/{ticket.id}

    Thank you,
    Support Team
    """
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [ticket.user.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.exception(f"Failed to send status email for ticket {ticket_id}")


@shared_task
def send_ticket_reply_email(message_id):
    try:
        message = TicketMessage.objects.select_related(
            'ticket', 'ticket__user', 'user'
        ).get(id=message_id)
    except TicketMessage.DoesNotExist:
        logger.warning(f"Message {message_id} not found for reply email")
        return

    ticket = message.ticket
    recipient = ticket.user if message.user != ticket.user else ticket.assigned_to
    if not recipient:
        logger.warning(f"No recipient for reply email on message {message_id}")
        return

    subject = f"New reply on ticket #{ticket.id}"
    body = f"""
    Hello {recipient.get_full_name() or recipient.email},

    {message.user.get_full_name() or message.user.email} replied to your ticket "{ticket.subject}":

    "{message.message[:200]}..."

    View the full conversation: {settings.FRONTEND_URL}/tickets/{ticket.id}

    Support Team
    """
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.exception(f"Failed to send reply email for message {message_id}")