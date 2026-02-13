# FILE: backend/apps/analytics/serializers.py
from rest_framework import serializers
from .models import DailyAggregate


class DailyAggregateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyAggregate
        fields = '__all__'
        # Make all fields read‑only by collecting actual field names
        read_only_fields = tuple(field.name for field in model._meta.fields)

    # Optional: if you prefer to explicitly list fields for security, replace fields = '__all__' with:
    # fields = [
    #     'id', 'date', 'total_users', 'active_users', 'new_users',
    #     'total_sales', 'total_orders', 'licenses_activated',
    #     'licenses_expired', 'total_usage_events', 'abuse_attempts',
    #     'created_at', 'updated_at'
    # ]