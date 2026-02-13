# FILE: backend/apps/analytics/views.py
from rest_framework import generics, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import DailyAggregate
from .serializers import DailyAggregateSerializer


class DailyAggregateListView(generics.ListAPIView):
    """
    List daily aggregates, most recent first.
    Supports filtering by date range and ordering.
    """
    queryset = DailyAggregate.objects.all().order_by('-date')
    serializer_class = DailyAggregateSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['date']
    ordering_fields = ['date', 'total_users', 'active_users', 'new_users',
                       'total_sales', 'total_orders', 'licenses_activated',
                       'licenses_expired', 'total_usage_events', 'abuse_attempts']
    ordering = ['-date']  # default ordering

    # Optional: use pagination to limit response size
    pagination_class = None  # Can be set to a custom pagination class if needed


class DailyAggregateDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific day's aggregate.
    Accepts primary key or date (via lookup_field customization).
    """
    queryset = DailyAggregate.objects.all()
    serializer_class = DailyAggregateSerializer
    permission_classes = [permissions.IsAdminUser]
    # If you want to allow lookup by date instead of pk, add:
    # lookup_field = 'date'   # and use the date in URL, e.g., /aggregates/2025-03-21/