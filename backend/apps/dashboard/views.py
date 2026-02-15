from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.utils import timezone
from datetime import timedelta

from backend.apps.analytics.models import DailyAggregate, CohortAggregate
from .models import DashboardSnapshot
from .serializers import DashboardStatsSerializer


class DashboardStatsView(APIView):
    """
    Returns a comprehensive set of statistics for the admin dashboard.
    Data is precomputed in a snapshot and cached for 5 minutes.
    """
    permission_classes = [permissions.IsAdminUser]

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def get(self, request):
        today = timezone.now().date()

        # Get the latest snapshot; if none exists, return 503 with explanation
        snapshot = DashboardSnapshot.objects.order_by('-created_at').first()
        if snapshot is None:
            return Response(
                {"detail": "Dashboard data not yet available. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Latest daily aggregate (small table, can be queried fresh)
        latest_daily = DailyAggregate.objects.order_by('-date').first()

        # Recent cohorts (last 6 weeks)
        cohorts = CohortAggregate.objects.filter(
            period='week',
            cohort_date__gte=today - timedelta(weeks=6)
        ).order_by('cohort_date', 'period_number')

        # Prepare response data
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

        serializer = DashboardStatsSerializer(data)
        return Response(serializer.data)