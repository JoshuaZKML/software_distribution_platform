# FILE: /backend/apps/accounts/tasks.py (CREATE NEW)
import logging
from celery import shared_task, Task
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import time

logger = logging.getLogger(__name__)


class BaseEmailTask(Task):
    """
    Base task class for email operations with retry logic.
    """
    max_retries = 3
    default_retry_delay = 60  # 1 minute
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)


@shared_task(base=BaseEmailTask)
def send_verification_email(user_id):
    """
    Send email verification link to new user.
    """
    from .models import User
    from .utils.verification import EmailVerificationToken
    
    try:
        user = User.objects.get(id=user_id)
        
        # Generate verification token
        token = EmailVerificationToken.generate_token(str(user.id), user.email)
        
        # Build verification URL
        verification_url = f"{settings.FRONTEND_URL}/verify-email/{token}"
        
        # Email context
        context = {
            'user': user,
            'verification_url': verification_url,
            'expiry_hours': 24,
            'support_email': settings.SUPPORT_EMAIL,
            'current_year': timezone.now().year,
        }
        
        # Render email templates
        html_content = render_to_string('accounts/email/verification.html', context)
        text_content = render_to_string('accounts/email/verification.txt', context)
        
        # Create email
        email = EmailMultiAlternatives(
            subject="Verify Your Email - Software Distribution Platform",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            reply_to=[settings.SUPPORT_EMAIL],
            headers={
                'X-Priority': '1',
                'X-Mailer': 'Software Distribution Platform',
            }
        )
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f"Verification email sent to {user.email}")
        return {
            'status': 'success',
            'message': f"Verification email sent to {user.email}",
            'user_id': str(user.id),
            'email': user.email
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for verification email")
        raise
    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        # Retry the task
        raise send_verification_email.retry(exc=e)


@shared_task(base=BaseEmailTask)
def send_password_reset_email(user_id, reset_token):
    """
    Send password reset email to user.
    """
    from .models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        # Build reset URL
        reset_url = f"{settings.FRONTEND_URL}/reset-password/{reset_token}"
        
        # Email context
        context = {
            'user': user,
            'reset_url': reset_url,
            'expiry_hours': 1,
            'support_email': settings.SUPPORT_EMAIL,
            'current_year': timezone.now().year,
            'ip_address': None,  # Would come from request if available
        }
        
        # Render email templates
        html_content = render_to_string('accounts/email/password_reset.html', context)
        text_content = render_to_string('accounts/email/password_reset.txt', context)
        
        # Create email
        email = EmailMultiAlternatives(
            subject="Reset Your Password - Software Distribution Platform",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            reply_to=[settings.SUPPORT_EMAIL],
            headers={
                'X-Priority': '1',
                'X-Mailer': 'Software Distribution Platform',
            }
        )
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        # Log password reset request
        from .models import SecurityLog
        SecurityLog.objects.create(
            actor=user,
            action='PASSWORD_RESET_REQUESTED',
            target=f"user:{user.id}",
            ip_address=context['ip_address'],
            user_agent='System Task',
            metadata={
                'email_sent_to': user.email,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        logger.info(f"Password reset email sent to {user.email}")
        return {
            'status': 'success',
            'message': f"Password reset email sent to {user.email}",
            'user_id': str(user.id),
            'email': user.email
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for password reset")
        raise
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        raise send_password_reset_email.retry(exc=e)


# FILE: /backend/apps/accounts/tasks.py (UPDATED – Enhanced device verification email task)

@shared_task(base=BaseEmailTask)
def send_device_verification_email(user_id, device_log_id, verification_token, verification_code):
    """
    Send device verification email with code.
    Enhanced version – uses DeviceVerificationManager to pass pre‑generated
    token and code, and a DeviceChangeLog record.
    """
    from .models import User, DeviceChangeLog
    from django.template.loader import render_to_string
    from django.core.mail import EmailMessage

    try:
        user = User.objects.get(id=user_id)
        device_log = DeviceChangeLog.objects.get(id=device_log_id)

        context = {
            'user': user,
            'device_fingerprint': device_log.new_fingerprint[:8] + '...',
            'verification_code': verification_code,
            'verification_url': f"{settings.FRONTEND_URL}/device-verify?token={verification_token}",
            'ip_address': device_log.ip_address,
            'user_agent': device_log.user_agent,
            'support_email': settings.SUPPORT_EMAIL,
            'current_year': timezone.now().year,
        }

        html_message = render_to_string('accounts/email/device_verification.html', context)
        text_message = render_to_string('accounts/email/device_verification.txt', context)

        email = EmailMessage(
            subject="Verify Your New Device - Software Distribution Platform",
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            reply_to=[settings.SUPPORT_EMAIL],
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)

        logger.info(f"Device verification email sent to {user.email} (log id: {device_log_id})")
        return {
            'status': 'success',
            'message': f"Device verification email sent to {user.email}",
            'user_id': str(user.id),
            'device_log_id': device_log_id,
        }

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for device verification")
        raise
    except DeviceChangeLog.DoesNotExist:
        logger.error(f"DeviceChangeLog {device_log_id} not found")
        raise
    except Exception as e:
        logger.error(f"Failed to send device verification email: {str(e)}")
        raise send_device_verification_email.retry(exc=e)


@shared_task(base=BaseEmailTask)
def send_welcome_email(user_id):
    """
    Send welcome email after successful verification.
    """
    from .models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        # Only send if user is verified
        if not user.is_verified:
            logger.warning(f"User {user_id} is not verified, skipping welcome email")
            return {
                'status': 'skipped',
                'message': 'User not verified'
            }
        
        # Email context
        context = {
            'user': user,
            'dashboard_url': f"{settings.FRONTEND_URL}/dashboard",
            'support_email': settings.SUPPORT_EMAIL,
            'current_year': timezone.now().year,
            'features': [
                'Download software',
                'Manage licenses',
                'Access support',
                'Update profile',
            ]
        }
        
        # Render email templates
        html_content = render_to_string('accounts/email/welcome.html', context)
        text_content = render_to_string('accounts/email/welcome.txt', context)
        
        # Create email
        email = EmailMultiAlternatives(
            subject="Welcome to Software Distribution Platform!",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            reply_to=[settings.SUPPORT_EMAIL],
        )
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f"Welcome email sent to {user.email}")
        return {
            'status': 'success',
            'message': f"Welcome email sent to {user.email}"
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for welcome email")
        raise
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        raise send_welcome_email.retry(exc=e)


@shared_task(base=BaseEmailTask)
def send_admin_notification_email(user_id, notification_type, data):
    """
    Send notification email to admins for important events.
    """
    from .models import User
    
    try:
        # Get all admin users
        admins = User.objects.filter(
            role__in=[User.Role.ADMIN, User.Role.SUPER_ADMIN],
            is_active=True,
            is_verified=True
        )
        
        if not admins.exists():
            logger.warning("No admin users found for notification")
            return {
                'status': 'skipped',
                'message': 'No admin users found'
            }
        
        # Get user if provided
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        
        # Email context
        context = {
            'notification_type': notification_type,
            'user': user,
            'data': data,
            'timestamp': timezone.now().isoformat(),
            'current_year': timezone.now().year,
        }
        
        # Render email templates
        html_content = render_to_string('accounts/email/admin_notification.html', context)
        text_content = render_to_string('accounts/email/admin_notification.txt', context)
        
        # Send to all admins
        admin_emails = [admin.email for admin in admins]
        
        email = EmailMultiAlternatives(
            subject=f"Admin Notification: {notification_type}",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=admin_emails,
            reply_to=[settings.SUPPORT_EMAIL],
            headers={
                'X-Priority': '1',
                'Importance': 'high',
            }
        )
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f"Admin notification sent to {len(admin_emails)} admins")
        return {
            'status': 'success',
            'message': f"Admin notification sent to {len(admin_emails)} admins",
            'notification_type': notification_type
        }
        
    except Exception as e:
        logger.error(f"Failed to send admin notification: {str(e)}")
        raise send_admin_notification_email.retry(exc=e)


@shared_task
def cleanup_expired_sessions():
    """
    Clean up expired user sessions.
    """
    from .models import UserSession
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Delete sessions inactive for more than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        expired_sessions = UserSession.objects.filter(
            last_activity__lt=cutoff_date
        )
        
        count = expired_sessions.count()
        expired_sessions.delete()
        
        logger.info(f"Cleaned up {count} expired sessions")
        return {
            'status': 'success',
            'message': f"Cleaned up {count} expired sessions"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


@shared_task
def cleanup_failed_login_attempts():
    """
    Clean up old failed login attempts.
    """
    from .models import SecurityLog
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Delete failed login attempts older than 90 days
        cutoff_date = timezone.now() - timedelta(days=90)
        old_attempts = SecurityLog.objects.filter(
            action='LOGIN_FAILED',
            created_at__lt=cutoff_date
        )
        
        count = old_attempts.count()
        old_attempts.delete()
        
        logger.info(f"Cleaned up {count} old failed login attempts")
        return {
            'status': 'success',
            'message': f"Cleaned up {count} old failed login attempts"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup failed login attempts: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


@shared_task
def send_account_summary_email(user_id):
    """
    Send periodic account summary email to user.
    """
    from .models import User, UserSession
    
    try:
        user = User.objects.get(id=user_id)
        
        # Only send to active, verified users
        if not user.is_active or not user.is_verified:
            return {
                'status': 'skipped',
                'message': 'User not active or verified'
            }
        
        # Get recent activity
        recent_sessions = UserSession.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-last_activity')[:5]
        
        # Email context
        context = {
            'user': user,
            'recent_sessions': recent_sessions,
            'dashboard_url': f"{settings.FRONTEND_URL}/dashboard",
            'support_email': settings.SUPPORT_EMAIL,
            'current_year': timezone.now().year,
            'summary_period': 'week',
        }
        
        # Render email templates
        html_content = render_to_string('accounts/email/account_summary.html', context)
        text_content = render_to_string('accounts/email/account_summary.txt', context)
        
        # Create email
        email = EmailMultiAlternatives(
            subject="Your Weekly Account Summary - Software Distribution Platform",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            reply_to=[settings.SUPPORT_EMAIL],
        )
        email.attach_alternative(html_content, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f"Account summary email sent to {user.email}")
        return {
            'status': 'success',
            'message': f"Account summary email sent to {user.email}"
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for account summary")
        raise
    except Exception as e:
        logger.error(f"Failed to send account summary email: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


@shared_task
def process_email_queue():
    """
    Process queued emails (for future implementation with email queue model).
    """
    # This is a placeholder for future email queue implementation
    # Currently, emails are sent directly via tasks
    
    logger.info("Email queue processor ran (no queue implemented yet)")
    return {
        'status': 'success',
        'message': 'Email queue processor executed'
    }