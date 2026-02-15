"""
Dashboard snapshot models for precomputed analytics.
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
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

    # ----- NEW: Snapshot date for uniqueness and easier querying -----
    snapshot_date = models.DateField(
        unique=True,
        editable=False,
        db_index=True,
        null=True,          # Allow null for existing rows; new rows will be set
        help_text=_("Date of the snapshot (derived from created_at)")
    )

    # ----- NEW: Metrics version to handle definition changes -----
    metrics_version = models.CharField(
        max_length=20,
        default='v1',
        editable=False,
        help_text=_("Version of the metric definitions used for this snapshot")
    )

    # Totals (all time)
    total_users = models.PositiveIntegerField(default=0)
    total_paid_users = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(
        max_digits=18, decimal_places=2,   # Increased from 12 → 18 for enterprise scale
        default=Decimal('0.00')
    )
    total_licenses_activated = models.PositiveIntegerField(default=0)
    total_abuse_attempts = models.PositiveIntegerField(default=0)

    # Last 30 days
    active_users_last_30 = models.PositiveIntegerField(default=0)
    new_users_last_30 = models.PositiveIntegerField(default=0)
    revenue_last_30 = models.DecimalField(
        max_digits=18, decimal_places=2,   # Increased from 12 → 18
        default=Decimal('0.00')
    )

    # Snapshot timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("dashboard snapshot")
        verbose_name_plural = _("dashboard snapshots")
        ordering = ['-created_at']
        get_latest_by = 'created_at'
        # ----- NEW: Database constraints to ensure data integrity -----
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_paid_users__lte=models.F('total_users')),
                name='paid_users_lte_total_users'
            ),
            models.CheckConstraint(
                check=models.Q(active_users_last_30__lte=models.F('total_users')),
                name='active_users_lte_total_users'
            ),
            # Add more constraints as needed
        ]
        indexes = [
            models.Index(fields=['snapshot_date']),  # already indexed via db_index, but explicit
        ]

    def __str__(self):
        return f"Dashboard snapshot {self.created_at}"

    def save(self, *args, **kwargs):
        # Automatically set snapshot_date from created_at (for new rows)
        if not self.snapshot_date and self.created_at:
            self.snapshot_date = self.created_at.date()
        super().save(*args, **kwargs)