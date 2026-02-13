# FILE: /backend/apps/licenses/tasks.py
"""
Celery tasks for license lifecycle management.

- send_license_activation_email:   Sends activation instructions + license file.
- (Revocation email is handled in `backend.apps.accounts.tasks` – do NOT redefine here.)
- send_license_expiry_reminders:   Daily task to send expiry reminders.
- send_expiry_reminder_email:      Individual email task for a licence about to expire.
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import ActivationCode

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="licenses.tasks.send_license_activation_email")
def send_license_activation_email(user_id, activation_code_id):
    """
    Sends an activation email containing:
      - Human‑readable activation code
      - Software name and version
      - Expiry date
      - (Optional) Encrypted license file (can be attached or embedded)
    """
    try:
        user = User.objects.get(pk=user_id)
        code_obj = ActivationCode.objects.select_related(
            'software_version__software'
        ).get(pk=activation_code_id)

        # Prepare context for email templates
        context = {
            'user': user,
            'activation_code': code_obj.human_code,          # ✅ Correct field name
            'software': code_obj.software_version.software.name if code_obj.software_version else 'N/A',
            'version': code_obj.software_version.version_number if code_obj.software_version else 'N/A',
            'expires_at': code_obj.expires_at,
            'support_email': settings.SUPPORT_EMAIL,
            'frontend_url': settings.FRONTEND_URL,
        }

        # Render email content
        html_content = render_to_string('licenses/email/activation.html', context)
        text_content = strip_tags(html_content)

        # Construct email
        email = EmailMultiAlternatives(
            subject=f"License Activated: {context['software']}",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            reply_to=[settings.SUPPORT_EMAIL],
        )
        email.attach_alternative(html_content, "text/html")

        # ------------------------------------------------------------------
        # OPTIONAL: Attach encrypted license file (V1.1 with hardware binding)
        # Uncomment when ready to generate per‑user license files.
        # from .utils.encryption import LicenseEncryptionManager
        # manager = LicenseEncryptionManager()
        # license_package = manager.create_license_file_with_binding(
        #     license_data={
        #         'activation_id': str(code_obj.id),
        #         'human_code': code_obj.human_code,
        #         'software': context['software'],
        #     },
        #     hardware_id=code_obj.device_fingerprint,   # if available
        #     expiry_days=code_obj.batch.expires_in_days if code_obj.batch else 365
        # )
        # email.attach('license.lic', license_package, 'application/json')
        # ------------------------------------------------------------------

        email.send(fail_silently=False)
        logger.info(f"Activation email sent to {user.email} for code {code_obj.human_code}")
        return f"Activation email sent to {user.email}"

    except User.DoesNotExist:
        logger.error(f"Activation email failed: User {user_id} does not exist.")
        return f"Failed to send email: User {user_id} not found."
    except ActivationCode.DoesNotExist:
        logger.error(f"Activation email failed: ActivationCode {activation_code_id} does not exist.")
        return f"Failed to send email: ActivationCode {activation_code_id} not found."
    except Exception as e:
        logger.exception(f"Unexpected error sending activation email: {e}")
        return f"Failed to send email: {str(e)}"


# ============================================================================
# ⚠️  CRITICAL: License Revocation Email is implemented in `accounts.tasks`
# ============================================================================
# from backend.apps.accounts.tasks import send_license_revocation_email
#
# DO NOT redefine send_license_revocation_email here.
# Celery task names must be unique; redefining causes registry conflicts.
#
# Revocation is tightly coupled with user account status (bans, refunds, security).
# Keeping it in accounts.tasks respects separation of concerns and avoids circular imports.
# ============================================================================


# ============================================================================
# EXPIRY REMINDER TASKS (updated 2026‑02‑13 with full email implementation)
# ============================================================================

@shared_task(name="licenses.tasks.send_license_expiry_reminders")
def send_license_expiry_reminders():
    """
    Send reminders for licences expiring soon.
    Runs daily (configured via Celery beat).
    Intervals: 21, 14, 7, 1 days before expiry, and on the expiry day (0).
    Uses the `expiry_reminders_sent` JSONField to avoid duplicate reminders.
    """
    today = timezone.now().date()
    intervals = [21, 14, 7, 1, 0]  # 0 = expired today

    for days in intervals:
        target_date = today + timedelta(days=days)
        filter_kwargs = {'expires_at__date': target_date} if days != 0 else {'expires_at__date': today}

        codes = ActivationCode.objects.filter(
            **filter_kwargs,
            status='ACTIVATED',            # only active licences
            software__is_active=True       # software still available
        ).exclude(
            expiry_reminders_sent__contains=[days]   # already sent
        ).select_related('user', 'software')

        for code in codes:
            # Schedule individual email (allows per‑code rate limiting)
            send_expiry_reminder_email.delay(
                code_id=str(code.id),
                days_left=days
            )


@shared_task(
    name="licenses.tasks.send_expiry_reminder_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3
)
def send_expiry_reminder_email(self, code_id, days_left):
    """
    Send a single expiry reminder email for a specific activation code.
    Idempotent: checks `expiry_reminders_sent` before sending.
    Marks reminder as sent only after successful email dispatch.
    """
    from .models import ActivationCode
    code = ActivationCode.objects.select_related('user', 'software').get(id=code_id)

    # Skip if already sent (idempotency)
    if days_left in code.expiry_reminders_sent:
        return

    user = code.user
    if not user or not user.email:
        logger.warning(f"Expiry reminder for code {code.human_code}: no user/email, skipping.")
        return

    # Build subject
    if days_left > 0:
        subject = f"Your {code.software.name} licence expires in {days_left} day{'s' if days_left != 1 else ''}"
    else:
        subject = f"Your {code.software.name} licence has expired"

    # Generate unsubscribe token – now relying on the User model method added earlier
    try:
        unsubscribe_token = user.get_unsubscribe_token()
        # The token already contains uid, so we pass it as a single parameter
        unsubscribe_url = f"{settings.FRONTEND_URL}/unsubscribe?token={unsubscribe_token}"
    except AttributeError:
        # Fallback (should not happen, but kept for safety)
        unsubscribe_token = "unsubscribe_token_placeholder"
        unsubscribe_url = f"{settings.FRONTEND_URL}/unsubscribe?uid={user.id}&token={unsubscribe_token}"
        logger.warning("User.get_unsubscribe_token() not implemented; using fallback URL.")

    context = {
        'user': user,
        'software': code.software,
        'code': code.human_code,
        'days_left': days_left,
        'expiry_date': code.expires_at,
        'renewal_url': f"{settings.FRONTEND_URL}/renew/{code.id}",
        'support_email': settings.SUPPORT_EMAIL,
        'unsubscribe_url': unsubscribe_url,
        'current_year': timezone.now().year,      # added for template
    }

    html_body = render_to_string('licenses/email/expiry_reminder.html', context)
    text_body = render_to_string('licenses/email/expiry_reminder.txt', context)

    # ------------------------------------------------------------------------
    # ACTUAL EMAIL SENDING – using EmailMultiAlternatives directly
    # ------------------------------------------------------------------------
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            reply_to=[settings.SUPPORT_EMAIL],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)

        # Mark as sent only after successful send
        code.expiry_reminders_sent.append(days_left)
        code.last_reminder_sent_at = timezone.now()
        code.save(update_fields=['expiry_reminders_sent', 'last_reminder_sent_at'])

        logger.info(f"Expiry reminder sent to {user.email} for code {code.human_code} (days_left={days_left})")
        return {'status': 'success', 'email': user.email}

    except Exception as e:
        logger.exception(f"Failed to send expiry reminder to {user.email}: {e}")
        # Do not mark as sent; allow retry via Celery autoretry
        raise  # re-raise to trigger retry