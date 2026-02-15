"""
Dashboard snapshot models for precomputed analytics.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class DashboardSnapshot(models.Model):
    """
    Stores precomputed dashboard statistics.
    Updated periodically by a Celery task.

    Design note: This table grows over time. For long‑term production use,
    consider implementing a retention policy (e.g., delete snapshots older
    than 30 days) or switch to a singleton pattern with update-in-place.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Totals (all time)
    total_users = models.PositiveIntegerField(default=0)
    total_paid_users = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal('0.00')  # explicit Decimal for financial precision
    )
    total_licenses_activated = models.PositiveIntegerField(default=0)
    total_abuse_attempts = models.PositiveIntegerField(default=0)

    # Last 30 days
    active_users_last_30 = models.PositiveIntegerField(default=0)
    new_users_last_30 = models.PositiveIntegerField(default=0)
    revenue_last_30 = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal('0.00')
    )

    # Snapshot timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # index for fast latest()

    class Meta:
        verbose_name = _("dashboard snapshot")
        verbose_name_plural = _("dashboard snapshots")
        ordering = ['-created_at']
        get_latest_by = 'created_at'

    def __str__(self):
        return f"Dashboard snapshot {self.created_at}"