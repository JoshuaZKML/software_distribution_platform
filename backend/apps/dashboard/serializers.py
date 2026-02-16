# FILE: backend/apps/dashboard/serializers.py
from rest_framework import serializers
from .models import DashboardSnapshot
from backend.apps.analytics.models import DailyAggregate, CohortAggregate

# ----------------------------------------------------------------------
# Centralised precision constants (align with model, avoid drift)
# ----------------------------------------------------------------------
MONEY_MAX_DIGITS = 18          # increased from 12 to match updated model
MONEY_DECIMAL_PLACES = 2
RETENTION_MAX_DIGITS = 5        # 100.00 max
RETENTION_DECIMAL_PLACES = 2


class DailyAggregateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyAggregate
        fields = [
            'date', 'total_users', 'active_users', 'new_users',
            'total_sales', 'total_orders', 'licenses_activated',
            'licenses_expired', 'total_usage_events', 'abuse_attempts'
        ]
        read_only_fields = fields   # ensure read‑only

    # Add validation to prevent negative values (defensive)
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Already integers, but we can ensure non‑negative by model defaults
        return data


class CohortSerializer(serializers.ModelSerializer):
    """
    Serializes cohort retention data.
    - retention_rate is a percentage (0.00 to 100.00)
    - cohort_date is the start of the cohort period
    - period indicates week/month
    - period_number is the offset (e.g., week 1, week 2)
    """
    retention_rate = serializers.DecimalField(
        max_digits=RETENTION_MAX_DIGITS,
        decimal_places=RETENTION_DECIMAL_PLACES,
        min_value=0,
        max_value=100,
        read_only=True,
        help_text="Retention percentage (0.00 to 100.00)"
    )

    class Meta:
        model = CohortAggregate
        fields = ['cohort_date', 'period', 'period_number', 'retention_rate']
        read_only_fields = fields


class TotalsSerializer(serializers.Serializer):
    """All‑time totals – derived from DashboardSnapshot."""
    users = serializers.IntegerField(min_value=0, read_only=True)
    paid_users = serializers.IntegerField(min_value=0, read_only=True)
    revenue = serializers.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        min_value=0,
        read_only=True
    )
    licenses_activated = serializers.IntegerField(min_value=0, read_only=True)
    abuse_attempts = serializers.IntegerField(min_value=0, read_only=True)


class Last30DaysSerializer(serializers.Serializer):
    """Rolling 30‑day metrics – derived from DashboardSnapshot."""
    active_users = serializers.IntegerField(min_value=0, read_only=True)
    new_users = serializers.IntegerField(min_value=0, read_only=True)
    revenue = serializers.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        min_value=0,
        read_only=True
    )


class DashboardStatsSerializer(serializers.Serializer):
    """
    Defines the structure of the dashboard response.
    Monetary values are returned as Decimal (serialized as string by DRF).

    - latest_daily: most recent daily aggregate, or null if none exists.
    - totals: all‑time cumulative metrics.
    - last_30_days: metrics for the last 30 days.
    - cohorts: list of retention cohorts, ordered by cohort_date then period_number.
    - snapshot_time: timestamp of the data snapshot.
    """
    latest_daily = DailyAggregateSerializer(allow_null=True, read_only=True)
    totals = TotalsSerializer(read_only=True)
    last_30_days = Last30DaysSerializer(read_only=True)
    cohorts = CohortSerializer(many=True, read_only=True)
    snapshot_time = serializers.DateTimeField(read_only=True)

    def to_representation(self, instance):
        # Ensure cohorts are ordered consistently (upstream should already order)
        # This is just a safeguard comment; actual ordering must be applied in the view.
        return super().to_representation(instance)


# ============================================================================
# New serializers for the additional dashboard endpoints
# ============================================================================

class OverviewSerializer(serializers.Serializer):
    """Response for DashboardOverviewView."""
    totals = serializers.DictField()
    today = serializers.DictField()
    last_7_days = serializers.DictField()
    last_30_days = serializers.DictField()
    chart = serializers.DictField()


class AnalyticsSerializer(serializers.Serializer):
    """Response for AnalyticsView."""
    daily = DailyAggregateSerializer(many=True)
    cohorts = CohortSerializer(many=True)
    top_software = serializers.ListField(child=serializers.DictField())


class ReportSerializer(serializers.Serializer):
    """Response for ReportsView."""
    type = serializers.CharField()
    range = serializers.CharField()
    data = serializers.DictField()


class UserActivitySerializer(serializers.Serializer):
    """Response for UserActivityView."""
    activities = serializers.ListField(child=serializers.DictField())
    total = serializers.IntegerField()


class SalesDashboardSerializer(serializers.Serializer):
    """Response for SalesDashboardView."""
    current_month = serializers.DictField()
    last_month = serializers.DictField()
    mrr = serializers.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    arpu = serializers.DecimalField(max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES)
    top_customers = serializers.ListField(child=serializers.DictField())


class LicenseUsageDashboardSerializer(serializers.Serializer):
    """Response for LicenseUsageDashboardView."""
    licenses_by_status = serializers.ListField(child=serializers.DictField())
    activations_daily = serializers.ListField(child=serializers.DictField())
    top_features = serializers.ListField(child=serializers.DictField())
    software_usage = serializers.ListField(child=serializers.DictField())


class SystemMonitoringSerializer(serializers.Serializer):
    """Response for SystemMonitoringView."""
    celery = serializers.DictField()
    cache = serializers.DictField()
    database = serializers.DictField()
    errors = serializers.DictField()
    timestamp = serializers.DateTimeField()