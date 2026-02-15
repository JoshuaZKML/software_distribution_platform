# FILE: backend/apps/analytics/tasks.py
import logging
from datetime import timedelta, datetime

from celery import shared_task
from django.db.models import Sum, Count
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache  # added for cohort lock

from .models import DailyAggregate, CohortAggregate  # added CohortAggregate
from backend.apps.payments.models import Payment
from backend.apps.licenses.models import ActivationCode
from backend.apps.products.models import SoftwareUsageEvent
from backend.apps.security.models import AbuseAttempt
from backend.apps.accounts.models import UserSession  # added for login events

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


@shared_task(name="analytics.tasks.compute_cohorts")
def compute_cohorts():
    """
    Compute weekly and monthly retention cohorts using actual login events (UserSession).
    Runs weekly (Sunday 2 AM) and processes the last 12 weeks and 12 months.
    Uses a cache lock to prevent overlapping executions.
    """
    lock_id = "cohort_computation_lock"
    # Acquire lock (expires after 6 hours – task should finish within that)
    if not cache.add(lock_id, "locked", timeout=60*60*6):
        logger.info("Cohort computation already running, skipping.")
        return

    try:
        today = timezone.now().date()

        # --- Weekly cohorts (last 12 weeks) ---
        for weeks_ago in range(1, 13):
            # Calculate Monday of that week
            cohort_start = today - timedelta(weeks=weeks_ago)
            # Adjust to Monday (weekday 0 = Monday)
            cohort_start = cohort_start - timedelta(days=cohort_start.weekday())
            cohort_end = cohort_start + timedelta(days=6)

            # Users who registered in that week
            user_ids = list(
                User.objects.filter(
                    date_joined__date__gte=cohort_start,
                    date_joined__date__lte=cohort_end
                ).values_list('id', flat=True)
            )
            total = len(user_ids)
            if total == 0:
                continue

            # For each subsequent week up to today
            max_weeks = (today - cohort_start).days // 7
            for week_offset in range(1, max_weeks + 1):
                period_start = cohort_start + timedelta(weeks=week_offset)
                period_end = period_start + timedelta(days=6)

                # Count distinct users who had a session created in this period
                retained = UserSession.objects.filter(
                    user_id__in=user_ids,
                    created_at__date__gte=period_start,
                    created_at__date__lte=period_end
                ).values('user_id').distinct().count()

                rate = (retained / total) * 100 if total else 0

                CohortAggregate.objects.update_or_create(
                    cohort_date=cohort_start,
                    period='week',
                    period_number=week_offset,
                    defaults={
                        'user_count': total,
                        'retained_count': retained,
                        'retention_rate': round(rate, 2),
                    }
                )

        # --- Monthly cohorts (last 12 months) ---
        for months_ago in range(1, 13):
            # First day of the month, months_ago months ago
            cohort_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            for _ in range(months_ago - 1):
                cohort_start = (cohort_start.replace(day=1) - timedelta(days=1)).replace(day=1)
            # Now cohort_start is the first day of that month
            # Compute end of month
            if cohort_start.month == 12:
                cohort_end = cohort_start.replace(year=cohort_start.year+1, month=1, day=1) - timedelta(days=1)
            else:
                cohort_end = cohort_start.replace(month=cohort_start.month+1, day=1) - timedelta(days=1)

            user_ids = list(
                User.objects.filter(
                    date_joined__date__gte=cohort_start,
                    date_joined__date__lte=cohort_end
                ).values_list('id', flat=True)
            )
            total = len(user_ids)
            if total == 0:
                continue

            # For each subsequent month up to today
            current = cohort_start
            month_offset = 1
            while current <= today:
                period_start = current.replace(day=1)
                if period_start.month == 12:
                    period_end = period_start.replace(year=period_start.year+1, month=1, day=1) - timedelta(days=1)
                else:
                    period_end = period_start.replace(month=period_start.month+1, day=1) - timedelta(days=1)

                # Skip the cohort month itself (offset 0)
                if period_start > cohort_start:
                    retained = UserSession.objects.filter(
                        user_id__in=user_ids,
                        created_at__date__gte=period_start,
                        created_at__date__lte=period_end
                    ).values('user_id').distinct().count()

                    rate = (retained / total) * 100 if total else 0

                    CohortAggregate.objects.update_or_create(
                        cohort_date=cohort_start,
                        period='month',
                        period_number=month_offset,
                        defaults={
                            'user_count': total,
                            'retained_count': retained,
                            'retention_rate': round(rate, 2),
                        }
                    )
                    month_offset += 1

                # Move to next month
                if current.month == 12:
                    current = current.replace(year=current.year+1, month=1)
                else:
                    current = current.replace(month=current.month+1)

    finally:
        cache.delete(lock_id)