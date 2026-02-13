# FILE: backend/apps/analytics/tasks.py
import logging
from datetime import timedelta, datetime

from celery import shared_task
from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import DailyAggregate
from backend.apps.payments.models import Payment
from backend.apps.licenses.models import ActivationCode
from backend.apps.products.models import SoftwareUsageEvent
from backend.apps.security.models import AbuseAttempt

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(
    name="analytics.tasks.compute_daily_aggregates",
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def compute_daily_aggregates(self, target_date=None):
    """
    Compute and store daily aggregates for a given date.
    If target_date is None, computes for yesterday.
    Designed to run daily at 1 AM (for yesterday) and can be called
    manually with a specific date for backfills.
    """
    # Determine the target date (always a date object in UTC)
    if target_date is None:
        target_date = timezone.now().date() - timedelta(days=1)
    else:
        # Ensure we have a date object (if string is passed, convert)
        if isinstance(target_date, str):
            target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

    logger.info(f"Starting daily aggregate computation for {target_date}")

    # Define datetime range for the target day (UTC)
    start_datetime = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
    end_datetime = start_datetime + timedelta(days=1)

    # Check if already computed (idempotency)
    agg, created = DailyAggregate.objects.get_or_create(
        date=target_date,
        defaults={
            'total_users': 0,  # temporary; will be updated after aggregation
            'active_users': 0,
            'new_users': 0,
            'total_sales': 0,
            'total_orders': 0,
            'licenses_activated': 0,
            'licenses_expired': 0,
            'total_usage_events': 0,
            'abuse_attempts': 0,
        }
    )
    if not created:
        logger.info(f"Daily aggregate for {target_date} already exists. Updating with fresh data.")
    else:
        logger.info(f"Creating new daily aggregate for {target_date}")

    # Compute aggregates (using efficient datetime ranges, not __date)
    try:
        # User metrics
        total_users = User.objects.filter(date_joined__lt=end_datetime).count()
        active_users = User.objects.filter(
            last_login__gte=end_datetime - timedelta(days=30)
        ).count()
        new_users = User.objects.filter(
            date_joined__gte=start_datetime,
            date_joined__lt=end_datetime
        ).count()

        # Payment metrics (assuming status 'completed')
        completed_payments = Payment.objects.filter(
            created_at__gte=start_datetime,
            created_at__lt=end_datetime,
            status='completed'
        )
        total_sales = completed_payments.aggregate(Sum('amount'))['amount__sum'] or 0
        total_orders = completed_payments.count()

        # License metrics
        licenses_activated = ActivationCode.objects.filter(
            activated_at__gte=start_datetime,
            activated_at__lt=end_datetime
        ).count()
        licenses_expired = ActivationCode.objects.filter(
            expires_at__gte=start_datetime,
            expires_at__lt=end_datetime,
            status='ACTIVATED'
        ).count()

        # Usage events
        total_usage_events = SoftwareUsageEvent.objects.filter(
            created_at__gte=start_datetime,
            created_at__lt=end_datetime
        ).count()

        # Abuse attempts
        abuse_attempts = AbuseAttempt.objects.filter(
            created_at__gte=start_datetime,
            created_at__lt=end_datetime
        ).count()

        # Update the aggregate
        agg.total_users = total_users
        agg.active_users = active_users
        agg.new_users = new_users
        agg.total_sales = total_sales
        agg.total_orders = total_orders
        agg.licenses_activated = licenses_activated
        agg.licenses_expired = licenses_expired
        agg.total_usage_events = total_usage_events
        agg.abuse_attempts = abuse_attempts
        agg.save()

        logger.info(
            f"Daily aggregate for {target_date} completed. "
            f"Users: total={total_users}, active={active_users}, new={new_users}; "
            f"Sales: {total_sales} on {total_orders} orders; "
            f"Licenses: +{licenses_activated}, -{licenses_expired}; "
            f"Usage events: {total_usage_events}; Abuse: {abuse_attempts}"
        )

    except Exception as exc:
        logger.error(f"Failed to compute daily aggregates for {target_date}: {exc}")
        # Retry with exponential backoff (Celery default)
        raise self.retry(exc=exc)