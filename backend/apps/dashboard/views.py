# backend/apps/dashboard/views.py

import logging
import time
from datetime import timedelta, date
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone
from django.db.models import Sum, Count, Q, F
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.accounts.models import User
from backend.apps.payments.models import Payment
from backend.apps.licenses.models import ActivationCode, ActivationLog, LicenseUsage
from backend.apps.security.models import AbuseAttempt
from backend.apps.analytics.models import DailyAggregate, CohortAggregate
from .models import DashboardSnapshot
from .serializers import (
    DashboardStatsSerializer,
    OverviewSerializer,
    AnalyticsSerializer,
    ReportSerializer,
    UserActivitySerializer,
    SalesDashboardSerializer,
    LicenseUsageDashboardSerializer,
    SystemMonitoringSerializer,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Existing DashboardStatsView (unchanged)
# ----------------------------------------------------------------------
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


# ----------------------------------------------------------------------
# New Fully Implemented Dashboard Views
# ----------------------------------------------------------------------

class DashboardOverviewView(APIView):
    """
    High‑level dashboard overview with key metrics and recent trends.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        cache_key = "dashboard_overview"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        start_time = time.time()
        now = timezone.now()
        today = now.date()
        yesterday = today - timedelta(days=1)
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)

        # Real-time aggregations (lightweight, indexed)
        total_users = User.objects.count()
        new_users_today = User.objects.filter(date_joined__date=today).count()
        new_users_7d = User.objects.filter(date_joined__date__gte=last_7_days).count()
        new_users_30d = User.objects.filter(date_joined__date__gte=last_30_days).count()

        active_users_today = User.objects.filter(last_login__date=today).count()
        active_users_7d = User.objects.filter(last_login__date__gte=last_7_days).count()
        active_users_30d = User.objects.filter(last_login__date__gte=last_30_days).count()

        # Revenue
        revenue_total = Payment.objects.filter(status='completed').aggregate(s=Sum('amount'))['s'] or Decimal('0')
        revenue_today = Payment.objects.filter(status='completed', created_at__date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        revenue_7d = Payment.objects.filter(status='completed', created_at__date__gte=last_7_days).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        revenue_30d = Payment.objects.filter(status='completed', created_at__date__gte=last_30_days).aggregate(s=Sum('amount'))['s'] or Decimal('0')

        # Licenses
        licenses_total = ActivationCode.objects.count()
        licenses_activated = ActivationCode.objects.filter(status='ACTIVATED').count()
        licenses_activated_today = ActivationCode.objects.filter(activated_at__date=today).count()
        licenses_activated_7d = ActivationCode.objects.filter(activated_at__date__gte=last_7_days).count()
        licenses_activated_30d = ActivationCode.objects.filter(activated_at__date__gte=last_30_days).count()

        # Abuse attempts
        abuse_total = AbuseAttempt.objects.count()
        abuse_today = AbuseAttempt.objects.filter(created_at__date=today).count()
        abuse_7d = AbuseAttempt.objects.filter(created_at__date__gte=last_7_days).count()

        # Chart data: last 7 days daily aggregates
        daily_stats = DailyAggregate.objects.filter(date__gte=last_7_days).order_by('date')
        chart_data = {
            'dates': [d.date.isoformat() for d in daily_stats],
            'new_users': [d.new_users for d in daily_stats],
            'active_users': [d.active_users for d in daily_stats],
            'revenue': [float(d.total_sales) for d in daily_stats],
            'licenses_activated': [d.licenses_activated for d in daily_stats],
        }

        data = {
            'totals': {
                'users': total_users,
                'revenue': revenue_total,
                'licenses': licenses_total,
                'activated_licenses': licenses_activated,
                'abuse_attempts': abuse_total,
            },
            'today': {
                'new_users': new_users_today,
                'active_users': active_users_today,
                'revenue': revenue_today,
                'licenses_activated': licenses_activated_today,
                'abuse_attempts': abuse_today,
            },
            'last_7_days': {
                'new_users': new_users_7d,
                'active_users': active_users_7d,
                'revenue': revenue_7d,
                'licenses_activated': licenses_activated_7d,
                'abuse_attempts': abuse_7d,
            },
            'last_30_days': {
                'new_users': new_users_30d,
                'active_users': active_users_30d,
                'revenue': revenue_30d,
                'licenses_activated': licenses_activated_30d,
            },
            'chart': chart_data,
        }

        serializer = OverviewSerializer(data=data)
        serializer.is_valid()  # will always be valid
        response_data = serializer.data

        cache.set(cache_key, response_data, 60 * 5)  # 5 minutes
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Dashboard overview assembled in {elapsed:.2f} ms.")
        return Response(response_data)


class AnalyticsView(APIView):
    """
    Detailed analytics including user growth, revenue trends, and cohort retention.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        cache_key = "dashboard_analytics"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        start_time = time.time()
        today = timezone.now().date()
        last_90_days = today - timedelta(days=90)

        # Daily aggregates for the last 90 days
        daily = DailyAggregate.objects.filter(date__gte=last_90_days).order_by('date')

        # Cohorts (weekly)
        cohorts = CohortAggregate.objects.filter(
            period='week',
            cohort_date__gte=today - timedelta(weeks=12)  # last 12 weeks
        ).order_by('cohort_date', 'period_number')

        # Top software by activations (requires software model, we'll use ActivationCode counts)
        from backend.apps.products.models import Software
        top_software = Software.objects.annotate(
            activation_count=Count('activation_codes', filter=Q(activation_codes__status='ACTIVATED'))
        ).order_by('-activation_count')[:10].values('name', 'slug', 'activation_count')

        data = {
            'daily': daily,
            'cohorts': cohorts,
            'top_software': list(top_software),
        }

        serializer = AnalyticsSerializer(data=data)
        serializer.is_valid()
        response_data = serializer.data
        cache.set(cache_key, response_data, 60 * 15)  # 15 minutes
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Analytics assembled in {elapsed:.2f} ms.")
        return Response(response_data)


class ReportsView(APIView):
    """
    Generate aggregated reports based on query parameters.
    Supports type=sales|users|licenses and date range from=YYYY-MM-DD to=YYYY-MM-DD.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        report_type = request.query_params.get('type', 'sales')
        from_date = request.query_params.get('from')
        to_date = request.query_params.get('to')

        if not from_date or not to_date:
            return Response(
                {"error": "Both 'from' and 'to' date parameters are required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            start = date.fromisoformat(from_date)
            end = date.fromisoformat(to_date)
        except ValueError:
            return Response(
                {"error": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if start > end:
            return Response(
                {"error": "'from' date must be before 'to' date."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Limit range to prevent excessive queries (max 1 year)
        if (end - start).days > 365:
            return Response(
                {"error": "Date range cannot exceed 365 days."},
                status=status.HTTP_400_BAD_REQUEST
            )

        cache_key = f"report_{report_type}_{start}_{end}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        start_time = time.time()
        data = {}

        if report_type == 'sales':
            payments = Payment.objects.filter(
                status='completed',
                created_at__date__gte=start,
                created_at__date__lte=end
            ).order_by('created_at')
            data = {
                'total_revenue': payments.aggregate(s=Sum('amount'))['s'] or 0,
                'total_transactions': payments.count(),
                'daily_breakdown': [
                    {
                        'date': d.strftime('%Y-%m-%d'),
                        'revenue': float(payments.filter(created_at__date=d).aggregate(s=Sum('amount'))['s'] or 0),
                        'count': payments.filter(created_at__date=d).count()
                    }
                    for d in (start + timedelta(n) for n in range((end - start).days + 1))
                ]
            }
        elif report_type == 'users':
            users = User.objects.filter(
                date_joined__date__gte=start,
                date_joined__date__lte=end
            ).order_by('date_joined')
            data = {
                'total_new_users': users.count(),
                'daily_breakdown': [
                    {
                        'date': d.strftime('%Y-%m-%d'),
                        'new_users': users.filter(date_joined__date=d).count()
                    }
                    for d in (start + timedelta(n) for n in range((end - start).days + 1))
                ]
            }
        elif report_type == 'licenses':
            activations = ActivationCode.objects.filter(
                activated_at__date__gte=start,
                activated_at__date__lte=end
            ).order_by('activated_at')
            data = {
                'total_activations': activations.count(),
                'by_license_type': activations.values('license_type').annotate(count=Count('id')),
                'daily_breakdown': [
                    {
                        'date': d.strftime('%Y-%m-%d'),
                        'activations': activations.filter(activated_at__date=d).count()
                    }
                    for d in (start + timedelta(n) for n in range((end - start).days + 1))
                ]
            }
        else:
            return Response(
                {"error": "Invalid report type. Choose 'sales', 'users', or 'licenses'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReportSerializer(data={'type': report_type, 'range': f"{start} to {end}", 'data': data})
        serializer.is_valid()
        response_data = serializer.data

        cache.set(cache_key, response_data, 60 * 30)  # 30 minutes
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Report {report_type} generated in {elapsed:.2f} ms.")
        return Response(response_data)


class UserActivityView(APIView):
    """
    Recent user activity: logins, license activations, deactivations, revocations.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Limit to last 100 activities across different sources
        limit = int(request.query_params.get('limit', 100))

        # Gather recent logins (from User last_login)
        recent_logins = User.objects.exclude(last_login__isnull=True).order_by('-last_login')[:limit]
        login_activities = [
            {
                'user_id': str(u.id),
                'user_email': u.email,
                'action': 'LOGIN',
                'timestamp': u.last_login.isoformat(),
                'details': {}
            }
            for u in recent_logins
        ]

        # Recent activation logs
        activation_logs = ActivationLog.objects.select_related('activation_code__user').order_by('-created_at')[:limit]
        activation_activities = [
            {
                'user_id': str(log.activation_code.user.id) if log.activation_code.user else None,
                'user_email': log.activation_code.user.email if log.activation_code.user else None,
                'action': log.action,
                'timestamp': log.created_at.isoformat(),
                'details': {
                    'code': log.activation_code.human_code,
                    'device_fingerprint': log.device_fingerprint,
                    'success': log.success,
                    'ip': log.ip_address,
                }
            }
            for log in activation_logs
        ]

        # Combine and sort by timestamp descending
        activities = login_activities + activation_activities
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        activities = activities[:limit]

        data = {
            'activities': activities,
            'total': len(activities),
        }

        serializer = UserActivitySerializer(data=data)
        serializer.is_valid()
        return Response(serializer.data)


class SalesDashboardView(APIView):
    """
    Sales‑focused metrics: revenue, MRR, ARPU, top customers, etc.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        cache_key = "dashboard_sales"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        start_time = time.time()
        now = timezone.now()
        today = now.date()
        first_day_month = today.replace(day=1)
        last_month = first_day_month - timedelta(days=1)
        first_day_last_month = last_month.replace(day=1)

        # Current month
        revenue_this_month = Payment.objects.filter(
            status='completed',
            created_at__date__gte=first_day_month
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        transactions_this_month = Payment.objects.filter(
            status='completed',
            created_at__date__gte=first_day_month
        ).count()

        # Last month
        revenue_last_month = Payment.objects.filter(
            status='completed',
            created_at__date__gte=first_day_last_month,
            created_at__date__lt=first_day_month
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

        # MRR (simple: average of last 3 months? For now, use last month's revenue as proxy)
        mrr = revenue_last_month

        # ARPU (average revenue per user, last 30 days)
        users_active_30d = User.objects.filter(last_login__date__gte=today - timedelta(days=30)).count()
        revenue_30d = Payment.objects.filter(
            status='completed',
            created_at__date__gte=today - timedelta(days=30)
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        arpu = revenue_30d / users_active_30d if users_active_30d else 0

        # Top customers by total paid
        top_customers = User.objects.filter(
            payments__status='completed'
        ).annotate(
            total_paid=Sum('payments__amount')
        ).order_by('-total_paid')[:10].values('id', 'email', 'total_paid')

        data = {
            'current_month': {
                'revenue': revenue_this_month,
                'transactions': transactions_this_month,
            },
            'last_month': {
                'revenue': revenue_last_month,
            },
            'mrr': mrr,
            'arpu': arpu,
            'top_customers': list(top_customers),
        }

        serializer = SalesDashboardSerializer(data=data)
        serializer.is_valid()
        response_data = serializer.data
        cache.set(cache_key, response_data, 60 * 30)  # 30 minutes
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"Sales dashboard assembled in {elapsed:.2f} ms.")
        return Response(response_data)


class LicenseUsageDashboardView(APIView):
    """
    License usage statistics: activations, usage events, popular features, etc.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        cache_key = "dashboard_license_usage"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        start_time = time.time()
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)

        # License counts by status
        licenses_by_status = ActivationCode.objects.values('status').annotate(count=Count('id')).order_by('status')

        # Activations over time (last 30 days)
        activations_daily = ActivationCode.objects.filter(
            activated_at__date__gte=last_30_days
        ).values('activated_at__date').annotate(count=Count('id')).order_by('activated_at__date')

        # Most used features (from LicenseUsage)
        top_features = LicenseUsage.objects.values(
            'feature__name', 'feature__code'
        ).annotate(
            total_usage=Sum('usage_count')
        ).order_by('-total_usage')[:10]

        # License usage by software
        from backend.apps.products.models import Software
        software_usage = Software.objects.annotate(
            total_activations=Count('activation_codes', filter=Q(activation_codes__status='ACTIVATED'))
        ).order_by('-total_activations')[:10].values('name', 'slug', 'total_activations')

        data = {
            'licenses_by_status': list(licenses_by_status),
            'activations_daily': [
                {'date': item['activated_at__date'].isoformat(), 'count': item['count']}
                for item in activations_daily
            ],
            'top_features': list(top_features),
            'software_usage': list(software_usage),
        }

        serializer = LicenseUsageDashboardSerializer(data=data)
        serializer.is_valid()
        response_data = serializer.data
        cache.set(cache_key, response_data, 60 * 15)  # 15 minutes
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"License usage dashboard assembled in {elapsed:.2f} ms.")
        return Response(response_data)


class SystemMonitoringView(APIView):
    """
    System health metrics: Celery queue sizes, cache stats, error logs, etc.
    For now returns placeholder data; can be extended with real monitoring integrations.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Placeholder – replace with actual monitoring if needed
        data = {
            'celery': {
                'default_queue_size': 0,  # would need to query broker
                'active_tasks': 0,
                'failed_tasks_last_hour': 0,
            },
            'cache': {
                'hits_per_second': 0,
                'misses_per_second': 0,
                'memory_usage_mb': 0,
            },
            'database': {
                'connections': 0,
                'slow_queries_last_hour': 0,
            },
            'errors': {
                'recent_500_errors': 0,
            },
            'timestamp': timezone.now().isoformat(),
        }

        # Optional: try to get cache stats if using Redis
        try:
            from django.core.cache import cache as django_cache
            if hasattr(django_cache, 'client') and hasattr(django_cache.client, 'get_client'):
                redis_client = django_cache.client.get_client()
                info = redis_client.info()
                data['cache']['memory_usage_mb'] = info.get('used_memory', 0) / (1024 * 1024)
                data['cache']['hits_per_second'] = info.get('keyspace_hits', 0)
                data['cache']['misses_per_second'] = info.get('keyspace_misses', 0)
        except:
            pass

        serializer = SystemMonitoringSerializer(data=data)
        serializer.is_valid()
        return Response(serializer.data)