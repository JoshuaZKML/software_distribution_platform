import logging
import time
from datetime import timedelta
from decimal import Decimal
from celery import shared_task
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.cache import cache
from backend.apps.accounts.models import User
from backend.apps.payments.models import Payment
from backend.apps.licenses.models import ActivationCode
from backend.apps.security.models import AbuseAttempt
from .models import DashboardSnapshot

logger = logging.getLogger(__name__)


@shared_task(name="dashboard.tasks.update_dashboard_snapshot")
def update_dashboard_snapshot():
    """
    Compute all dashboard statistics and store them in a snapshot.
    Runs every 10 minutes via Celery beat.

    Uses a distributed Redis lock to prevent overlapping executions.
    Wrapped in a database transaction for consistency.
    """
    lock_id = "dashboard_snapshot_lock"
    # Use Redis (or configured cache) with a 15-minute timeout
    if not cache.add(lock_id, "locked", timeout=60*15):
        logger.info("Dashboard snapshot update already running, skipping.")
        return

    start_time = time.time()
    try:
        now = timezone.now()
        last_30_days = now - timedelta(days=30)

        # All‑time totals (ensure indexes exist on status fields)
        total_users = User.objects.count()
        total_paid_users = User.objects.filter(
            payments__status='completed'
        ).distinct().count()  # Consider denormalizing a `is_paid` flag for large scale
        total_revenue = Payment.objects.filter(
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_licenses_activated = ActivationCode.objects.filter(
            status='ACTIVATED'
        ).count()
        total_abuse_attempts = AbuseAttempt.objects.count()

        # Last 30 days (using datetime filters to preserve index usage)
        active_users_last_30 = User.objects.filter(
            last_login__gte=last_30_days
        ).count()  # Note: `last_login` only tracks most recent; for true activity, use event logs.
        new_users_last_30 = User.objects.filter(
            date_joined__gte=last_30_days
        ).count()
        revenue_last_30 = Payment.objects.filter(
            status='completed',
            created_at__gte=last_30_days
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Create snapshot atomically
        with transaction.atomic():
            DashboardSnapshot.objects.create(
                total_users=total_users,
                total_paid_users=total_paid_users,
                total_revenue=total_revenue,
                total_licenses_activated=total_licenses_activated,
                total_abuse_attempts=total_abuse_attempts,
                active_users_last_30=active_users_last_30,
                new_users_last_30=new_users_last_30,
                revenue_last_30=revenue_last_30,
            )

        elapsed = time.time() - start_time
        logger.info(f"Dashboard snapshot updated successfully in {elapsed:.2f}s.")

    except Exception as e:
        logger.exception("Dashboard snapshot update failed.")
        # Optionally raise to trigger Celery retry
        raise
    finally:
        cache.delete(lock_id)