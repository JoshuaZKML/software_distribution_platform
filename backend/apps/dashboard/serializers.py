from rest_framework import serializers
from .models import DashboardSnapshot
from backend.apps.analytics.models import DailyAggregate, CohortAggregate


class DailyAggregateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyAggregate
        fields = [
            'date', 'total_users', 'active_users', 'new_users',
            'total_sales', 'total_orders', 'licenses_activated',
            'licenses_expired', 'total_usage_events', 'abuse_attempts'
        ]


class CohortSerializer(serializers.ModelSerializer):
    class Meta:
        model = CohortAggregate
        fields = ['cohort_date', 'period', 'period_number', 'retention_rate']


class TotalsSerializer(serializers.Serializer):
    users = serializers.IntegerField()
    paid_users = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    licenses_activated = serializers.IntegerField()
    abuse_attempts = serializers.IntegerField()


class Last30DaysSerializer(serializers.Serializer):
    active_users = serializers.IntegerField()
    new_users = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)


class DashboardStatsSerializer(serializers.Serializer):
    """
    Defines the structure of the dashboard response.
    Monetary values are returned as Decimal (serialized as string by DRF).
    """
    latest_daily = DailyAggregateSerializer(allow_null=True)
    totals = TotalsSerializer()
    last_30_days = Last30DaysSerializer()
    cohorts = CohortSerializer(many=True)
    snapshot_time = serializers.DateTimeField()