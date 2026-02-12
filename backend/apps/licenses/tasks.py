# FILE: /backend/apps/licenses/tasks.py
"""
Celery tasks for license lifecycle management.

- send_license_activation_email:   Sends activation instructions + license file.
- (Revocation email is handled in `backend.apps.accounts.tasks` – do NOT redefine here.)
"""
import logging
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.auth import get_user_model

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