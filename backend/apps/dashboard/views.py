#backend/apps/dashboard/views.py

import logging
import time
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from django.views.decorators.cache import cache_page
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.analytics.models import DailyAggregate, CohortAggregate
from .models import DashboardSnapshot
from .serializers import DashboardStatsSerializer

logger = logging.getLogger(__name__)


class DashboardStatsView(APIView):
    """
    Returns a comprehensive set of statistics for the admin dashboard.
    Data is precomputed in a snapshot and cached for 5 minutes.

    Cache is managed manually to avoid cross‑user contamination and to
    align with the snapshot update schedule.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        cache_key = "admin_dashboard_stats"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug("Dashboard stats served from cache.")
            return Response(cached_data)

        start_time = time.time()
        today = timezone.now().date()

        # Get the latest snapshot using the model's built‑in latest() method
        snapshot = DashboardSnapshot.objects.latest()
        if snapshot is None:
            # This should not happen if the Celery task has run at least once.
            return Response(
                {"detail": "Dashboard data not yet available. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Latest daily aggregate (small table, can be queried fresh)
        latest_daily = DailyAggregate.objects.order_by('-date').first()

        # Recent cohorts (last 6 weeks) – ensure indexes on (period, cohort_date)
        cohorts = CohortAggregate.objects.filter(
            period='week',
            cohort_date__gte=today - timedelta(weeks=6)
        ).order_by('cohort_date', 'period_number')

        # Assemble response data
        data = {
            'latest_daily': latest_daily,
            'totals': {
                'users': snapshot.total_users,
                'paid_users': snapshot.total_paid_users,
                'revenue': snapshot.total_revenue,
                'licenses_activated': snapshot.total_licenses_activated,
                'abuse_attempts': snapshot.total_abuse_attempts,
            },
            'last_30_days': {
                'active_users': snapshot.active_users_last_30,
                'new_users': snapshot.new_users_last_30,
                'revenue': snapshot.revenue_last_30,
            },
            'cohorts': cohorts,
            'snapshot_time': snapshot.created_at,
        }

        # Serialize (explicit instance argument for clarity)
        serializer = DashboardStatsSerializer(instance=data)
        response_data = serializer.data

        # Cache for 5 minutes (matches snapshot update cadence; snapshots every 10 min)
        cache.set(cache_key, response_data, 60 * 5)

        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Dashboard stats assembled in {elapsed:.2f} ms.")

        return Response(response_data)