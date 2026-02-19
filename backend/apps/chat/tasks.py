from celery import shared_task
from backend.apps.notifications.services import NotificationService
from django.contrib.auth import get_user_model
from .models import ChatSession

User = get_user_model()


@shared_task
def notify_admins_new_chat(session_id):
    try:
        session = ChatSession.objects.get(id=session_id)
    except ChatSession.DoesNotExist:
        return

    admins = User.objects.filter(role__in=['ADMIN', 'SUPER_ADMIN'])
    for admin in admins:
        NotificationService.send(
            user=admin,
            channel='in_app',
            subject='New chat request',
            body=f"{session.visitor_name} is waiting for support.",
            context={'session_id': str(session.id)}
        )