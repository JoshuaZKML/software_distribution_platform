"""
Payments models for Software Distribution Platform.
"""
import uuid
import hashlib
from datetime import timedelta
from decimal import Decimal  # added for Plan price default
from django.db import models, transaction
from django.db.models import F, Q, UniqueConstraint  # added UniqueConstraint
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings


# ----------------------------------------------------------------------
# AUDIT LOG MODEL – NEW, NON‑DISRUPTIVE ADDITION
# ----------------------------------------------------------------------

class GatewayEventLog(models.Model):
    """
    Immutable log of all payment gateway webhook events.
    Used for audit, replay detection, and reconciliation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway = models.CharField(max_length=20, db_index=True)
    event_type = models.CharField(max_length=50, db_index=True, blank=True, null=True)
    reference = models.CharField(max_length=255, db_index=True, blank=True, null=True)
    payload = models.JSONField()                         # Masked, parsed payload
    raw_payload = models.TextField(blank=True)           # Raw request body (for forensic replay)
    status_code = models.PositiveSmallIntegerField(default=200)
    error_message = models.TextField(blank=True)
    correlation_id = models.CharField(max_length=64, blank=True, db_index=True)
    payload_hash = models.CharField(max_length=64, unique=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("gateway event log")
        verbose_name_plural = _("gateway event logs")
        indexes = [
            models.Index(fields=["gateway", "-created_at"]),
            models.Index(fields=["reference", "gateway"]),
            models.Index(fields=["correlation_id"]),
        ]
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        # Generate a hash of the raw payload for deduplication
        if not self.payload_hash and self.raw_payload:
            self.payload_hash = hashlib.sha256(self.raw_payload.encode()).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.gateway} {self.event_type} {self.reference or ''}"


# ----------------------------------------------------------------------
# COUPON USAGE – ENHANCED WITH PARTIAL UNIQUE CONSTRAINTS
# ----------------------------------------------------------------------

class CouponUsage(models.Model):
    """
    Tracks individual usage of a coupon per user and per payment.
    Provides atomic usage counting and a clean audit trail.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coupon = models.ForeignKey(
        "Coupon",
        on_delete=models.CASCADE,
        related_name="usages"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coupon_usages"
    )
    payment = models.ForeignKey(
        "Payment",
        on_delete=models.CASCADE,
        related_name="coupon_usages",
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("coupon usage")
        verbose_name_plural = _("coupon usages")
        indexes = [
            models.Index(fields=["coupon", "user"]),
            models.Index(fields=["coupon", "created_at"]),
        ]
        constraints = [
            # Prevent duplicate tracking of the same coupon+user+payment when payment is non-null
            models.UniqueConstraint(
                fields=["coupon", "user", "payment"],
                name="unique_coupon_user_payment"
            ),
            # Prevent multiple null-payment usages of the same coupon by the same user
            models.UniqueConstraint(
                fields=["coupon", "user"],
                condition=Q(payment__isnull=True),
                name="unique_coupon_user_no_payment"
            ),
        ]

    def __str__(self):
        return f"Coupon {self.coupon.code} used by {self.user.email}"


# ----------------------------------------------------------------------
# PAYMENT MODEL – ENTERPRISE‑GRADE CONCURRENCY & FINANCIAL INTEGRITY
# ----------------------------------------------------------------------

class Payment(models.Model):
    """Payment transaction model."""

    # Status choices as TextChoices (backward‑compatible with existing strings)
    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        PROCESSING = "PROCESSING", _("Processing")
        COMPLETED = "COMPLETED", _("Completed")
        FAILED = "FAILED", _("Failed")
        REFUNDED = "REFUNDED", _("Refunded")
        CANCELLED = "CANCELLED", _("Cancelled")

    # Payment methods
    PAYMENT_METHODS = [
        ("STRIPE", "Stripe"),
        ("PAYPAL", "PayPal"),
        ("PAYSTACK", "Paystack"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("BANK_DEPOSIT", "Bank Deposit"),
        ("BITCOIN", "Bitcoin"),
        ("CRYPTO", "Cryptocurrency"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # User and software
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    software = models.ForeignKey(
        "products.Software",
        on_delete=models.CASCADE,
        related_name="payments"
    )

    # Payment details
    amount = models.DecimalField(_("amount"), max_digits=10, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default="USD")
    payment_method = models.CharField(
        _("payment method"),
        max_length=20,
        choices=PAYMENT_METHODS
    )

    # Status (using TextChoices)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    status_reason = models.TextField(_("status reason"), blank=True)

    # Transaction references – globally unique, nullable (NULL = not yet assigned)
    transaction_id = models.CharField(
        _("transaction ID"),
        max_length=255,
        blank=True,
        null=True,      # NULL for no ID, empty string is disallowed (prevents duplicate "")
        db_index=True,
        unique=True
    )
    gateway_reference = models.CharField(
        _("gateway reference"),
        max_length=255,
        blank=True,
        help_text=_("Reference ID from payment gateway")
    )

    # Metadata
    metadata = models.JSONField(_("metadata"), default=dict)

    # Timestamps
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    refunded_at = models.DateTimeField(_("refunded at"), null=True, blank=True)

    # Payment expiry (defaults to 24h after creation)
    expires_at = models.DateTimeField(
        _("expires at"),
        null=True,
        blank=True,
        help_text=_("Timestamp after which this payment is considered expired.")
    )

    # Allowed state transitions – used for validation (not a DB constraint)
    _STATUS_TRANSITIONS = {
        Status.PENDING: [Status.PROCESSING, Status.FAILED, Status.CANCELLED],
        Status.PROCESSING: [Status.COMPLETED, Status.FAILED],
        Status.COMPLETED: [Status.REFUNDED],
        Status.FAILED: [Status.PENDING],  # Allow retry
        Status.REFUNDED: [],
        Status.CANCELLED: [],
    }

    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["expires_at"]),  # For expiry cleanup jobs
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency}"

    @property
    def is_successful(self):
        return self.status == self.Status.COMPLETED

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def can_be_refunded(self):
        return self.status == self.Status.COMPLETED and not self.refunded_at

    @transaction.atomic
    def mark_completed(self, transaction_id="", gateway_reference=""):
        """
        Mark payment as completed.
        Uses select_for_update to prevent race conditions.
        This method is atomic and row‑locked.
        """
        # Reload with row lock to ensure we have the latest state
        payment = Payment.objects.select_for_update().get(pk=self.pk)
        # Validate transition
        if payment.status not in self._STATUS_TRANSITIONS.get(payment.status, []):
            raise ValidationError(f"Cannot transition from {payment.status} to {self.Status.COMPLETED}")
        payment.status = self.Status.COMPLETED
        payment.transaction_id = transaction_id or payment.transaction_id
        payment.gateway_reference = gateway_reference or payment.gateway_reference
        payment.completed_at = timezone.now()
        payment.save(update_fields=['status', 'transaction_id', 'gateway_reference', 'completed_at'])
        # Update current instance to reflect DB state
        self.status = payment.status
        self.transaction_id = payment.transaction_id
        self.gateway_reference = payment.gateway_reference
        self.completed_at = payment.completed_at
        return True

    @transaction.atomic
    def mark_failed(self, reason=""):
        """
        Mark payment as failed.
        Uses select_for_update to prevent race conditions.
        Atomic and row‑locked.
        """
        payment = Payment.objects.select_for_update().get(pk=self.pk)
        if payment.status not in self._STATUS_TRANSITIONS.get(payment.status, []):
            raise ValidationError(f"Cannot transition from {payment.status} to {self.Status.FAILED}")
        payment.status = self.Status.FAILED
        payment.status_reason = reason
        payment.save(update_fields=['status', 'status_reason'])
        self.status = payment.status
        self.status_reason = payment.status_reason
        return True

    def get_paystack_metadata(self):
        """
        Formats metadata for Paystack API initialisation.
        Stores the internal payment ID and software info for webhook correlation.
        """
        return {
            "payment_id": str(self.id),
            "software_id": str(self.software.id),
            "custom_fields": [
                {
                    "display_name": "Software",
                    "variable_name": "software",
                    "value": self.software.name
                }
            ]
        }

    def save(self, *args, **kwargs):
        """
        Validate status transition to prevent invalid state jumps.
        Skips the DB lookup for new instances to avoid an extra query.
        Auto‑set expires_at if not provided and this is a new record.
        """
        # Set default expiry for new payments
        if not self.expires_at and not self.pk:
            self.expires_at = timezone.now() + timedelta(hours=24)

        # Convert empty string to NULL for transaction_id (prevents uniqueness issues)
        if self.transaction_id == "":
            self.transaction_id = None

        # Only validate existing records; new records have no previous state.
        # Note: This validation is not race‑safe under concurrent updates.
        # For production, always use mark_completed() / mark_failed() which are row‑locked.
        if not self._state.adding:
            try:
                old = Payment.objects.get(pk=self.pk)
                if old.status != self.status:
                    allowed = self._STATUS_TRANSITIONS.get(old.status, [])
                    if self.status not in allowed:
                        raise ValidationError(
                            _("Cannot transition payment from %(old)s to %(new)s") %
                            {"old": old.status, "new": self.status}
                        )
            except Payment.DoesNotExist:
                pass
        super().save(*args, **kwargs)


# ============================================================================
# NEW PLAN MODEL – added without disruption (used by enhanced Subscription)
# ============================================================================

class Plan(models.Model):
    """
    Defines a subscription plan (pricing, billing interval, features).
    This is a new, independent model. Existing subscriptions are not affected.
    """
    INTERVAL_CHOICES = [
        ('month', 'Monthly'),
        ('year', 'Yearly'),
        ('lifetime', 'Lifetime'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)               # e.g., "Pro Monthly"
    code = models.SlugField(unique=True)                  # e.g., "pro_monthly"
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='USD')
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES)
    trial_days = models.PositiveIntegerField(default=0)
    features = models.JSONField(default=dict, blank=True)  # e.g., {"max_users": 10}
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("plan")
        verbose_name_plural = _("plans")
        ordering = ['sort_order', 'price']

    def __str__(self):
        return f"{self.name} ({self.currency} {self.price}/{self.interval})"


# ----------------------------------------------------------------------
# SUBSCRIPTION MODEL – enhanced with new fields (all nullable/optional)
# ----------------------------------------------------------------------

class Subscription(models.Model):
    """Subscription for recurring payments."""

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("CANCELLED", "Cancelled"),
        ("EXPIRED", "Expired"),
        ("SUSPENDED", "Suspended"),
        ("PENDING", "Pending"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )
    software = models.ForeignKey(
        "products.Software",
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )
    activation_code = models.OneToOneField(
        "licenses.ActivationCode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription"
    )

    # --- NEW: Plan reference (nullable, backward‑compatible) ---
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,          # Financial records should not be deleted
        null=True,
        blank=True,
        related_name="subscriptions"
    )

    # Subscription details
    plan_name = models.CharField(_("plan name"), max_length=100)
    billing_cycle = models.CharField(
        _("billing cycle"),
        max_length=20,
        choices=[
            ("MONTHLY", "Monthly"),
            ("QUARTERLY", "Quarterly"),
            ("YEARLY", "Yearly"),
            ("LIFETIME", "Lifetime"),
        ]
    )

    # Pricing
    amount = models.DecimalField(_("amount"), max_digits=10, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=3, default="USD")
    setup_fee = models.DecimalField(
        _("setup fee"),
        max_digits=10,
        decimal_places=2,
        default=0
    )

    # Status
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    # Dates
    start_date = models.DateTimeField(_("start date"))
    end_date = models.DateTimeField(_("end date"))
    next_billing_date = models.DateTimeField(_("next billing date"), null=True, blank=True)
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)

    # --- NEW: Period anchor fields (nullable, backward‑compatible) ---
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)   # actual termination time

    # Grace period for failed renewals (enterprise expectation)
    grace_period_until = models.DateTimeField(
        _("grace period until"),
        null=True,
        blank=True,
        help_text=_("If set, access remains valid until this date even after expiry.")
    )

    # Auto-renewal
    auto_renew = models.BooleanField(_("auto renew"), default=True)
    renewal_failed = models.BooleanField(_("renewal failed"), default=False)
    renewal_failure_reason = models.TextField(_("renewal failure reason"), blank=True)

    # --- NEW: Cancel‑at‑period‑end flag ---
    cancel_at_period_end = models.BooleanField(default=False)

    # Payment method
    payment_method = models.CharField(
        _("payment method"),
        max_length=20,
        choices=Payment.PAYMENT_METHODS
    )
    payment_gateway_id = models.CharField(
        _("payment gateway ID"),
        max_length=255,
        blank=True
    )

    # Metadata
    metadata = models.JSONField(_("metadata"), default=dict)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["software", "status"]),
            models.Index(fields=["status", "end_date"]),
            models.Index(fields=["next_billing_date"]),
            # --- NEW INDEXES ---
            models.Index(fields=["current_period_end"]),
        ]
        # --- NEW CONSTRAINT (safe only if no duplicate active subscriptions exist) ---
        constraints = [
            UniqueConstraint(
                fields=['user'],
                condition=Q(status='ACTIVE'),
                name='unique_active_subscription_per_user'
            ),
        ]

    def __str__(self):
        return f"Subscription {self.id} - {self.user.email}"

    @property
    def is_active(self):
        """Original active check – strictly between start and end date."""
        now = timezone.now()
        return (
            self.status == "ACTIVE" and
            self.start_date <= now <= self.end_date
        )

    @property
    def has_active_access(self):
        """
        Extended access check that includes the grace period.
        Use this for licensing decisions to avoid cutting off paying clients.
        """
        now = timezone.now()
        if self.status != "ACTIVE":
            return False
        if self.start_date <= now <= self.end_date:
            return True
        # Outside strict period – check grace window
        if self.grace_period_until and now <= self.grace_period_until:
            return True
        return False

    @property
    def days_remaining(self):
        if not self.is_active:
            return 0
        delta = self.end_date - timezone.now()
        return max(0, delta.days)

    def cancel(self, immediate=False):
        """Cancel subscription."""
        self.status = "CANCELLED"
        self.cancelled_at = timezone.now()
        self.auto_renew = False

        if immediate:
            self.end_date = timezone.now()

        self.save()
        return True

    def renew(self, new_end_date):
        """Renew subscription."""
        self.status = "ACTIVE"
        self.end_date = new_end_date
        self.renewal_failed = False
        self.renewal_failure_reason = ""
        self.save()
        return True

    # --- NEW VALIDATION METHOD (does not affect existing instances) ---
    def clean(self):
        """Validate period consistency for new fields (if present)."""
        if self.current_period_start and self.current_period_end:
            if self.current_period_start >= self.current_period_end:
                raise ValidationError("current_period_end must be after current_period_start")


# ----------------------------------------------------------------------
# INVOICE MODEL – enhanced with currency, status, and immutability
# ----------------------------------------------------------------------

class Invoice(models.Model):
    """Invoice for payment."""

    # --- NEW: status choices (backward‑compatible with existing is_paid) ---
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('paid', 'Paid'),
        ('void', 'Void'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="invoice"
    )

    # Invoice details
    invoice_number = models.CharField(
        _("invoice number"),
        max_length=50,
        unique=True,
        db_index=True
    )

    # Billing information
    billing_name = models.CharField(_("billing name"), max_length=255)
    billing_email = models.EmailField(_("billing email"))
    billing_phone = models.CharField(_("billing phone"), max_length=20, blank=True)
    billing_address = models.TextField(_("billing address"), blank=True)
    billing_city = models.CharField(_("billing city"), max_length=100, blank=True)
    billing_state = models.CharField(_("billing state"), max_length=100, blank=True)
    billing_country = models.CharField(_("billing country"), max_length=100, blank=True)
    billing_zip = models.CharField(_("billing zip"), max_length=20, blank=True)

    # Tax information
    tax_amount = models.DecimalField(_("tax amount"), max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(_("tax rate"), max_digits=5, decimal_places=2, default=0)
    tax_id = models.CharField(_("tax ID"), max_length=50, blank=True)

    # Totals
    subtotal = models.DecimalField(_("subtotal"), max_digits=10, decimal_places=2)
    discount = models.DecimalField(_("discount"), max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(_("total"), max_digits=10, decimal_places=2)

    # --- NEW FIELDS (currency, status) – default ensures existing rows get 'USD' and 'draft' ---
    currency = models.CharField(_("currency"), max_length=3, default='USD')
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    issued_at = models.DateTimeField(null=True, blank=True)   # set when issued

    # Original boolean field kept for backward compatibility
    is_paid = models.BooleanField(_("paid"), default=False)
    paid_at = models.DateTimeField(_("paid at"), null=True, blank=True)

    # File
    pdf_file = models.FileField(
        _("PDF file"),
        upload_to="invoices/%Y/%m/%d/",
        max_length=500,
        blank=True,
        null=True
    )

    # Metadata
    notes = models.TextField(_("notes"), blank=True)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['issued_at']),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.payment.user.email}"

    @property
    def amount_due(self):
        return self.total if not self.is_paid else 0

    # --- NEW VALIDATION AND LIFECYCLE METHODS ---
    def clean(self):
        """Validate amounts and immutability after issue."""
        # Ensure total = subtotal - discount + tax
        expected_total = self.subtotal - self.discount + self.tax_amount
        if self.total != expected_total:
            raise ValidationError(
                f"Total must equal subtotal - discount + tax ({expected_total})."
            )

        # Once issued, financial fields become immutable
        if self.pk:
            old = Invoice.objects.get(pk=self.pk)
            if old.status in ['issued', 'paid', 'void']:
                # Check if any financial field changed
                if (old.subtotal != self.subtotal or old.discount != self.discount or
                    old.tax_amount != self.tax_amount or old.total != self.total or
                    old.currency != self.currency):
                    raise ValidationError("Cannot modify financial fields after invoice is issued.")

    def save(self, *args, **kwargs):
        # Auto‑generate invoice number if missing and this is a draft
        if not self.invoice_number and self.status == 'draft':
            prefix = "INV"
            timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
            suffix = str(uuid.uuid4())[:8].upper()
            self.invoice_number = f"{prefix}-{timestamp}-{suffix}"

        # Ensure status and is_paid are consistent
        if self.status == 'paid' and not self.paid_at:
            self.paid_at = timezone.now()
        if self.status == 'paid':
            self.is_paid = True
        elif self.status == 'draft':
            self.is_paid = False

        self.full_clean()  # run validation before saving
        super().save(*args, **kwargs)

    def issue(self):
        """Transition from draft to issued."""
        if self.status != 'draft':
            raise ValidationError("Only draft invoices can be issued.")
        self.status = 'issued'
        self.issued_at = timezone.now()
        self.save()


# ----------------------------------------------------------------------
# OFFLINE PAYMENT MODEL – ENHANCED WITH ATOMIC TRANSACTIONS
# ----------------------------------------------------------------------

class OfflinePayment(models.Model):
    """Offline payment (bank transfer, deposit, etc.)."""

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("UNDER_REVIEW", "Under Review"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Payment relationship
    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="offline_payment"
    )

    # Receipt handling
    receipt_file = models.FileField(
        _("receipt file"),
        upload_to="receipts/%Y/%m/%d/",
        max_length=500,
        blank=True,
        null=True
    )
    receipt_text = models.TextField(_("receipt text"), blank=True)
    receipt_verified = models.BooleanField(_("receipt verified"), default=False)

    # Bank details (for bank transfer/deposit)
    bank_name = models.CharField(_("bank name"), max_length=100, blank=True)
    account_name = models.CharField(_("account name"), max_length=100, blank=True)
    account_number = models.CharField(_("account number"), max_length=50, blank=True)
    routing_number = models.CharField(_("routing number"), max_length=50, blank=True)
    reference_number = models.CharField(_("reference number"), max_length=100, blank=True)

    # Crypto details
    crypto_address = models.CharField(_("crypto address"), max_length=255, blank=True)
    crypto_tx_hash = models.CharField(_("crypto transaction hash"), max_length=255, blank=True)
    crypto_amount = models.DecimalField(
        _("crypto amount"),
        max_digits=20,
        decimal_places=8,
        null=True,
        blank=True
    )
    crypto_currency = models.CharField(_("crypto currency"), max_length=10, blank=True)

    # Status
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    # Approval tracking
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_payments"
    )
    reviewed_at = models.DateTimeField(_("reviewed at"), null=True, blank=True)
    review_notes = models.TextField(_("review notes"), blank=True)

    # Appeal system
    appeal_requested = models.BooleanField(_("appeal requested"), default=False)
    appeal_reason = models.TextField(_("appeal reason"), blank=True)
    appeal_reviewed = models.BooleanField(_("appeal reviewed"), default=False)
    appeal_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_appeals"
    )
    appeal_reviewed_at = models.DateTimeField(_("appeal reviewed at"), null=True, blank=True)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("offline payment")
        verbose_name_plural = _("offline payments")
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["payment", "status"]),
        ]

    def __str__(self):
        return f"Offline Payment {self.id} - {self.payment.user.email}"

    @property
    def can_be_approved(self):
        return self.status in ["PENDING", "UNDER_REVIEW"]

    @property
    def can_be_appealed(self):
        return self.status == "REJECTED" and not self.appeal_requested

    @transaction.atomic
    def approve(self, reviewed_by, notes=""):
        """Approve offline payment (atomic)."""
        if not self.can_be_approved:
            return False

        self.status = "APPROVED"
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()

        # Mark main payment as completed – also atomic and row‑locked
        self.payment.mark_completed(
            transaction_id=f"OFFLINE-{self.id}",
            gateway_reference="OFFLINE"
        )

        return True

    @transaction.atomic
    def reject(self, reviewed_by, notes=""):
        """Reject offline payment (atomic)."""
        if not self.can_be_approved:
            return False

        self.status = "REJECTED"
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()

        # Mark main payment as failed – also atomic and row‑locked
        self.payment.mark_failed(reason=f"Offline payment rejected: {notes}")

        return True

    def request_appeal(self, reason=""):
        """Request appeal for rejected payment."""
        if not self.can_be_appealed:
            return False

        self.appeal_requested = True
        self.appeal_reason = reason
        self.save()

        return True


# ----------------------------------------------------------------------
# COUPON MODEL – RACE‑SAFE ATOMIC USAGE
# ----------------------------------------------------------------------

class Coupon(models.Model):
    """Discount coupon."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Coupon details
    code = models.CharField(_("code"), max_length=50, unique=True, db_index=True)
    description = models.TextField(_("description"), blank=True)

    # Discount type
    discount_type = models.CharField(
        _("discount type"),
        max_length=10,
        choices=[
            ("PERCENTAGE", "Percentage"),
            ("FIXED", "Fixed Amount"),
        ],
        default="PERCENTAGE"
    )
    discount_value = models.DecimalField(
        _("discount value"),
        max_digits=10,
        decimal_places=2
    )
    max_discount = models.DecimalField(
        _("max discount"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Maximum discount amount (for percentage discounts)")
    )

    # Validity
    valid_from = models.DateTimeField(_("valid from"))
    valid_until = models.DateTimeField(_("valid until"))

    # Usage limits
    max_uses = models.IntegerField(
        _("max uses"),
        null=True,
        blank=True,
        help_text=_("Maximum number of times this coupon can be used")
    )
    max_uses_per_user = models.IntegerField(
        _("max uses per user"),
        default=1,
        help_text=_("Maximum number of times a single user can use this coupon")
    )

    # Applicability
    applicable_software = models.ManyToManyField(
        "products.Software",
        blank=True,
        related_name="coupons",
        help_text=_("Leave empty to apply to all software")
    )
    minimum_purchase = models.DecimalField(
        _("minimum purchase"),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Minimum purchase amount required")
    )

    # Status
    is_active = models.BooleanField(_("active"), default=True)

    # Usage tracking
    times_used = models.IntegerField(_("times used"), default=0)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("coupon")
        verbose_name_plural = _("coupons")
        indexes = [
            models.Index(fields=["code", "is_active"]),
            models.Index(fields=["valid_from", "valid_until"]),
        ]

    def __str__(self):
        return f"Coupon: {self.code}"

    @property
    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and
            self.valid_from <= now <= self.valid_until and
            (self.max_uses is None or self.times_used < self.max_uses)
        )

    def calculate_discount(self, amount):
        """Calculate discount amount for given purchase amount."""
        if not self.is_valid:
            return 0

        if amount < self.minimum_purchase:
            return 0

        if self.discount_type == "PERCENTAGE":
            discount = (amount * self.discount_value) / 100
            if self.max_discount:
                discount = min(discount, self.max_discount)
        else:
            discount = self.discount_value

        return min(discount, amount)

    def can_be_used_by(self, user):
        """
        Legacy usage check – uses metadata JSON field.
        Non‑disruptive; kept for backward compatibility.
        """
        from .models import Payment

        if not self.is_valid:
            return False

        # Check per-user usage limit (old method)
        user_usage = Payment.objects.filter(
            user=user,
            metadata__contains={"coupon_code": self.code}
        ).count()

        return user_usage < self.max_uses_per_user

    def can_be_used_by_v2(self, user):
        """
        Improved usage check using dedicated CouponUsage model.
        More performant and accurate.
        """
        if not self.is_valid:
            return False
        usage_count = self.usages.filter(user=user).count()
        return usage_count < self.max_uses_per_user

    @transaction.atomic
    def apply_usage(self, user, payment=None):
        """
        Atomically record that this coupon was used by a user.
        Uses select_for_update to prevent race conditions on the coupon row.
        DB unique constraints on CouponUsage prevent duplicate usage.
        Returns True if usage was recorded, False if limit exceeded.
        """
        # Lock the coupon row to prevent concurrent increments
        coupon = Coupon.objects.select_for_update().get(pk=self.pk)

        # Check global limit
        if coupon.max_uses is not None and coupon.times_used >= coupon.max_uses:
            return False

        # Check per-user limit using the new model
        if coupon.max_uses_per_user is not None:
            user_usage_count = coupon.usages.filter(user=user).count()
            if user_usage_count >= coupon.max_uses_per_user:
                return False

        # Increment atomic counter
        coupon.times_used = F('times_used') + 1
        coupon.save(update_fields=['times_used'])

        # Create audit record – unique constraints will raise IntegrityError if duplicate
        CouponUsage.objects.create(
            coupon=coupon,
            user=user,
            payment=payment
        )

        # Refresh from DB to get updated times_used
        coupon.refresh_from_db()
        return True