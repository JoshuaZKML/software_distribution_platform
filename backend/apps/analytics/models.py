# FILE: backend/apps/analytics/models.py
"""
Analytics models for aggregated daily statistics.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings  # used for ExportJob ForeignKey


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


class ExportJob(models.Model):
    """
    Tracks asynchronous export jobs.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    EXPORT_TYPE_CHOICES = [
        ('daily_aggregates', 'Daily Aggregates'),
        ('users', 'Users'),
        ('payments', 'Payments'),
        ('licenses', 'Licenses'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    export_type = models.CharField(max_length=50, choices=EXPORT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    parameters = models.JSONField(default=dict, blank=True)  # e.g., date range
    file = models.FileField(upload_to='exports/', null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("export job")
        verbose_name_plural = _("export jobs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.export_type} – {self.status}"


class CohortAggregate(models.Model):
    """
    Pre‑computed retention cohorts.
    Uses actual login events (UserSession) for accurate retention.
    """
    PERIOD_CHOICES = [
        ('week', 'Week'),
        ('month', 'Month'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cohort_date = models.DateField(db_index=True)  # start of cohort (Monday for weeks, 1st of month for months)
    period = models.CharField(max_length=5, choices=PERIOD_CHOICES)
    period_number = models.PositiveIntegerField()  # e.g., week 1, week 2, month 1, month 2
    user_count = models.PositiveIntegerField()      # total users in this cohort
    retained_count = models.PositiveIntegerField()  # users who logged in during the period
    retention_rate = models.DecimalField(            # precise percentage
        max_digits=5,
        decimal_places=2,
        help_text="Percentage (0.00 to 100.00)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("cohort aggregate")
        verbose_name_plural = _("cohort aggregates")
        unique_together = ('cohort_date', 'period', 'period_number')
        indexes = [
            models.Index(fields=['period', 'cohort_date']),  # for filtering by period and date
        ]
        ordering = ['cohort_date', 'period_number']

    def __str__(self):
        return f"{self.get_period_display()} {self.cohort_date} – period {self.period_number}"