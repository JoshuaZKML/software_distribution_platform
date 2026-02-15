import logging
import time
from datetime import timedelta
from decimal import Decimal
from celery import shared_task
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from backend.apps.accounts.models import User
from backend.apps.payments.models import Payment
from backend.apps.licenses.models import ActivationCode
from backend.apps.security.models import AbuseAttempt
from .models import DashboardSnapshot

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Configuration – can be overridden in Django settings
# ----------------------------------------------------------------------
SNAPSHOT_LOCK_TIMEOUT = getattr(settings, 'DASHBOARD_SNAPSHOT_LOCK_TIMEOUT', 60 * 15)      # 15 minutes
SNAPSHOT_RETENTION_DAYS = getattr(settings, 'DASHBOARD_SNAPSHOT_RETENTION_DAYS', 90)        # keep 90 days
SNAPSHOT_METRICS_VERSION = getattr(settings, 'DASHBOARD_SNAPSHOT_METRICS_VERSION', 'v1')


@shared_task(
    name="dashboard.tasks.update_dashboard_snapshot",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    retry_jitter=True
)
def update_dashboard_snapshot(self):
    """
    Compute all dashboard statistics and store them in a snapshot.
    Runs every 10 minutes via Celery beat.

    Uses a distributed Redis lock to prevent overlapping executions.
    Wrapped in a database transaction for better consistency.
    Automatically purges snapshots older than SNAPSHOT_RETENTION_DAYS.
    """
    lock_id = "dashboard_snapshot_lock"
    # Use Redis (or configured cache) with a timeout
    if not cache.add(lock_id, "locked", timeout=SNAPSHOT_LOCK_TIMEOUT):
        logger.info("Dashboard snapshot update already running, skipping.")
        return

    start_time = time.time()
    try:
        now = timezone.now()
        last_30_days = now - timedelta(days=30)

        # All computations are performed inside a transaction to get a
        # slightly more consistent view (repeatable read would be stronger,
        # but this at least groups all reads together).
        with transaction.atomic():
            total_users = User.objects.count()
            total_paid_users = User.objects.filter(
                payments__status='completed'
            ).distinct().count()
            total_revenue = Payment.objects.filter(
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            total_licenses_activated = ActivationCode.objects.filter(
                status='ACTIVATED'
            ).count()
            total_abuse_attempts = AbuseAttempt.objects.count()

            active_users_last_30 = User.objects.filter(
                last_login__gte=last_30_days
            ).count()
            new_users_last_30 = User.objects.filter(
                date_joined__gte=last_30_days
            ).count()
            revenue_last_30 = Payment.objects.filter(
                status='completed',
                created_at__gte=last_30_days
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            # Create snapshot (now includes snapshot_date and metrics_version)
            DashboardSnapshot.objects.create(
                snapshot_date=now.date(),
                metrics_version=SNAPSHOT_METRICS_VERSION,
                total_users=total_users,
                total_paid_users=total_paid_users,
                total_revenue=total_revenue,
                total_licenses_activated=total_licenses_activated,
                total_abuse_attempts=total_abuse_attempts,
                active_users_last_30=active_users_last_30,
                new_users_last_30=new_users_last_30,
                revenue_last_30=revenue_last_30,
            )

            # Enforce retention policy: delete snapshots older than retention days
            retention_cutoff = now - timedelta(days=SNAPSHOT_RETENTION_DAYS)
            deleted_count, _ = DashboardSnapshot.objects.filter(
                created_at__lt=retention_cutoff
            ).delete()
            if deleted_count:
                logger.info(f"Deleted {deleted_count} old snapshots (retention {SNAPSHOT_RETENTION_DAYS} days).")

        elapsed = time.time() - start_time
        logger.info(f"Dashboard snapshot updated successfully in {elapsed:.2f}s.")

    except Exception as e:
        logger.exception("Dashboard snapshot update failed.")
        # Raise to trigger Celery retry (autoretry will handle it)
        raise
    finally:
        # Always release the lock, but be careful not to delete a lock that
        # might have been taken over by another worker after timeout expiry.
        # This simple delete is safe enough for most setups.
        cache.delete(lock_id)