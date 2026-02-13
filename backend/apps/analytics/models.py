# FILE: backend/apps/analytics/models.py
"""
Analytics models for aggregated daily statistics.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class DailyAggregate(models.Model):
    """
    Pre‑computed daily statistics for dashboards.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True, db_index=True)

    # User metrics
    total_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)  # logged in last 30 days
    new_users = models.PositiveIntegerField(default=0)

    # Payment metrics
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_orders = models.PositiveIntegerField(default=0)

    # License metrics
    licenses_activated = models.PositiveIntegerField(default=0)
    licenses_expired = models.PositiveIntegerField(default=0)

    # Software usage (from SoftwareUsageEvent)
    total_usage_events = models.PositiveIntegerField(default=0)

    # Security
    abuse_attempts = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("daily aggregate")
        verbose_name_plural = _("daily aggregates")
        ordering = ['-date']

    def __str__(self):
        return f"Aggregate for {self.date}"