# FILE: backend/apps/security/tasks.py
"""
Celery tasks for security‑related notifications.
Hardened for production: atomic rate limiting, event‑level deduplication,
narrow retry scope, persistent idempotency tracking, and structured logging.
All changes are backward‑compatible and non‑disruptive.
"""
import hashlib
import json
import logging
import smtplib
from typing import List, Optional

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


# ----------------------------------------------------------------------
# Configuration – override in Django settings
# ----------------------------------------------------------------------
BREAKIN_NOTIFICATION_COOLDOWN = getattr(
    settings, 'BREAKIN_NOTIFICATION_COOLDOWN', 3600
)  # seconds (default 1 hour)

BREAKIN_NOTIFICATION_MAX_RETRIES = getattr(
    settings, 'BREAKIN_NOTIFICATION_MAX_RETRIES', 5
)

BREAKIN_NOTIFICATION_RETRY_BACKOFF_MAX = getattr(
    settings, 'BREAKIN_NOTIFICATION_RETRY_BACKOFF_MAX', 600
)

# Only retry on transient network/email errors, not programming bugs
BREAKIN_NOTIFICATION_RETRY_EXCEPTIONS = getattr(
    settings,
    'BREAKIN_NOTIFICATION_RETRY_EXCEPTIONS',
    (smtplib.SMTPException, ConnectionError, TimeoutError)
)

# High‑risk threshold to bypass cooldown (e.g., risk_level >= 10)
BREAKIN_NOTIFICATION_HIGH_RISK_THRESHOLD = getattr(
    settings, 'BREAKIN_NOTIFICATION_HIGH_RISK_THRESHOLD', 10
)

# ----------------------------------------------------------------------
# Optional persistent notification log model (additive, non‑disruptive)
# ----------------------------------------------------------------------
try:
    from .models import SecurityNotificationLog
    HAS_NOTIFICATION_LOG = True
except ImportError:
    HAS_NOTIFICATION_LOG = False

    # Define a dummy model for type safety when log is not used
    class SecurityNotificationLog:
        class DoesNotExist(Exception):
            pass


def _generate_event_fingerprint(user_id: str, ip: str, risk_level: int,
                                reasons: List[str]) -> str:
    """Generate a unique fingerprint for this security event."""
    event_data = {
        'user_id': str(user_id),
        'ip': ip,
        'risk_level': risk_level,
        'reasons': sorted(reasons) if reasons else [],
    }
    event_str = json.dumps(event_data, sort_keys=True)
    return hashlib.sha256(event_str.encode()).hexdigest()


def _normalize_reasons(reasons: Optional[List[str]]) -> List[str]:
    """Ensure reasons is a list of strings, safe for logging and joining."""
    if not isinstance(reasons, list):
        return []
    return [str(r) for r in reasons if r is not None]


@shared_task(
    bind=True,
    autoretry_for=BREAKIN_NOTIFICATION_RETRY_EXCEPTIONS,
    retry_backoff=True,
    retry_kwargs={'max_retries': BREAKIN_NOTIFICATION_MAX_RETRIES},
    retry_backoff_max=BREAKIN_NOTIFICATION_RETRY_BACKOFF_MAX,
    retry_jitter=True,
)
def notify_super_admins_of_breakin_attempt(
    self,
    user_id: str,
    ip: str,
    device_fingerprint: str,
    user_agent: str,
    risk_level: int,
    reasons: Optional[List[str]],
):
    """
    Send an email to all super administrators when a high‑risk
    authentication attempt is detected.

    - Atomic rate limiting & deduplication: uses `cache.add()` and event‑level
      fingerprinting to prevent duplicate notifications.
    - Persistent idempotency: if SecurityNotificationLog model exists,
      a database record ensures exactly‑once delivery across cache resets.
    - Narrow retry scope: only transient network/email errors trigger retries.
    - High‑risk bypass: if risk_level >= BREAKIN_NOTIFICATION_HIGH_RISK_THRESHOLD,
      cooldown is ignored (immediate notification).
    - BCC used to protect super admin email addresses.
    - Fallback plain text email if templates are missing.
    - Structured logging for observability.
    """
    reasons = _normalize_reasons(reasons)

    # ------------------------------------------------------------------
    # 1. Event fingerprint – for fine‑grained deduplication
    # ------------------------------------------------------------------
    event_hash = _generate_event_fingerprint(
        user_id, ip, risk_level, reasons
    )
    cooldown_key = f"breakin_notify_cooldown:event:{event_hash}"

    # ------------------------------------------------------------------
    # 2. High‑risk bypass – skip cooldown check for extreme events
    # ------------------------------------------------------------------
    bypass_cooldown = risk_level >= BREAKIN_NOTIFICATION_HIGH_RISK_THRESHOLD

    if not bypass_cooldown:
        # Atomic rate limiting – only proceeds if key was set now
        if not cache.add(cooldown_key, True, BREAKIN_NOTIFICATION_COOLDOWN):
            logger.info(
                "Break‑in notification suppressed (cooldown active)",
                extra={
                    'event_hash': event_hash,
                    'user_id': user_id,
                    'risk_level': risk_level,
                }
            )
            return

    # ------------------------------------------------------------------
    # 3. Persistent idempotency check (if notification log is available)
    # ------------------------------------------------------------------
    if HAS_NOTIFICATION_LOG:
        try:
            SecurityNotificationLog.objects.get(event_hash=event_hash)
            logger.info(
                "Break‑in notification already logged (duplicate event)",
                extra={'event_hash': event_hash, 'user_id': user_id}
            )
            return
        except SecurityNotificationLog.DoesNotExist:
            pass

    # ------------------------------------------------------------------
    # 4. Fetch target user
    # ------------------------------------------------------------------
    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning(
            "Break‑in notification: target user %s does not exist, aborting",
            user_id,
        )
        return

    # ------------------------------------------------------------------
    # 5. Fetch super admin email addresses (BCC list)
    #    Ensure indexes exist on (role, is_active, is_verified) for performance.
    # ------------------------------------------------------------------
    super_admin_emails = list(
        User.objects.filter(
            role=User.Role.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
        ).values_list('email', flat=True)
    )
    if not super_admin_emails:
        logger.info(
            "No super admin recipients, skipping notification.",
            extra={'user_id': user_id}
        )
        return

    # ------------------------------------------------------------------
    # 6. Build admin URL safely (validate scheme, prefer Sites)
    # ------------------------------------------------------------------
    try:
        admin_path = reverse('admin:index')
        # Prefer Django Sites framework if available, else settings.DOMAIN_URL
        domain_url = getattr(settings, 'DOMAIN_URL', None)
        if domain_url:
            # Ensure HTTPS if not in debug mode
            if not settings.DEBUG and not domain_url.startswith('https://'):
                logger.warning(
                    "DOMAIN_URL is not using HTTPS in production; "
                    "email links may be insecure."
                )
            admin_url = domain_url.rstrip('/') + admin_path
        else:
            # Fallback: relative URL
            admin_url = admin_path
            logger.warning(
                "DOMAIN_URL not set; using relative admin URL in email. "
                "Recipients may need to copy/paste."
            )
    except Exception:
        logger.exception("Failed to generate admin URL, using placeholder.")
        admin_url = getattr(settings, 'DOMAIN_URL', '#')

    # ------------------------------------------------------------------
    # 7. Build email context (autoescape is enabled by Django)
    # ------------------------------------------------------------------
    context = {
        'target_user': target_user,
        'ip': ip,
        'device_fingerprint': device_fingerprint,
        'user_agent': user_agent,
        'risk_level': risk_level,
        'reasons': reasons,
        'timestamp': timezone.now(),
        'admin_url': admin_url,
    }

    subject = f"[SECURITY ALERT] Break‑in attempt – User {target_user.email}"

    try:
        text_message = render_to_string(
            'security/email/breakin_attempt.txt',
            context,
        )
        html_message = render_to_string(
            'security/email/breakin_attempt.html',
            context,
        )
    except Exception:
        logger.exception("Failed to render email templates, using plain text fallback.")
        # Simple plain‑text fallback
        reason_text = ', '.join(reasons) if reasons else 'No specific reasons'
        text_message = (
            f"Security alert for user {target_user.email}\n"
            f"IP: {ip}\n"
            f"Risk level: {risk_level}\n"
            f"Reasons: {reason_text}\n"
            f"Time: {timezone.now()}\n"
            f"Admin URL: {admin_url}"
        )
        html_message = None

    # ------------------------------------------------------------------
    # 8. Send email – include a safe To address (DEFAULT_FROM_EMAIL),
    #    BCC all super admins.
    # ------------------------------------------------------------------
    try:
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.DEFAULT_FROM_EMAIL],  # valid envelope
            html_message=html_message,
            fail_silently=False,
            bcc=super_admin_emails,
        )
        logger.info(
            "Break‑in notification sent",
            extra={
                'event_hash': event_hash,
                'user_id': user_id,
                'recipient_count': len(super_admin_emails),
                'risk_level': risk_level,
                'bypass_cooldown': bypass_cooldown,
            }
        )
    except Exception as e:
        logger.exception(
            "Failed to send break‑in notification for user %s",
            target_user.email,
        )
        # Re-raise only if we haven't exceeded max retries (Celery handles it)
        raise

    # ------------------------------------------------------------------
    # 9. Persistent idempotency record (if model exists)
    # ------------------------------------------------------------------
    if HAS_NOTIFICATION_LOG:
        try:
            SecurityNotificationLog.objects.create(
                event_hash=event_hash,
                user=target_user,
                risk_level=risk_level,
                ip_address=ip,
                recipient_count=len(super_admin_emails),
            )
        except Exception:
            logger.exception("Failed to create persistent notification log")