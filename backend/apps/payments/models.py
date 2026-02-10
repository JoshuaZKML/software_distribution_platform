"""
Payments models for Software Distribution Platform.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings

class Payment(models.Model):
    """Payment transaction model."""
    
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
        ("CANCELLED", "Cancelled"),
    ]
    
    PAYMENT_METHODS = [
        ("STRIPE", "Stripe"),
        ("PAYPAL", "PayPal"),
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
    
    # Status
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )
    status_reason = models.TextField(_("status reason"), blank=True)
    
    # Transaction references
    transaction_id = models.CharField(
        _("transaction ID"),
        max_length=255,
        blank=True,
        db_index=True
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
    
    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency}"
    
    @property
    def is_successful(self):
        return self.status == "COMPLETED"
    
    @property
    def is_pending(self):
        return self.status == "PENDING"
    
    @property
    def can_be_refunded(self):
        return self.status == "COMPLETED" and not self.refunded_at
    
    def mark_completed(self, transaction_id="", gateway_reference=""):
        """Mark payment as completed."""
        self.status = "COMPLETED"
        self.transaction_id = transaction_id
        self.gateway_reference = gateway_reference
        self.completed_at = timezone.now()
        self.save()
        return True
    
    def mark_failed(self, reason=""):
        """Mark payment as failed."""
        self.status = "FAILED"
        self.status_reason = reason
        self.save()
        return True

class Invoice(models.Model):
    """Invoice for payment."""
    
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
    
    # Status
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
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.payment.user.email}"
    
    @property
    def amount_due(self):
        return self.total if not self.is_paid else 0

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
    
    def approve(self, reviewed_by, notes=""):
        """Approve offline payment."""
        if not self.can_be_approved:
            return False
        
        self.status = "APPROVED"
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
        
        # Mark main payment as completed
        self.payment.mark_completed(
            transaction_id=f"OFFLINE-{self.id}",
            gateway_reference="OFFLINE"
        )
        
        return True
    
    def reject(self, reviewed_by, notes=""):
        """Reject offline payment."""
        if not self.can_be_approved:
            return False
        
        self.status = "REJECTED"
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
        
        # Mark main payment as failed
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
    
    # Auto-renewal
    auto_renew = models.BooleanField(_("auto renew"), default=True)
    renewal_failed = models.BooleanField(_("renewal failed"), default=False)
    renewal_failure_reason = models.TextField(_("renewal failure reason"), blank=True)
    
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
        ]
    
    def __str__(self):
        return f"Subscription {self.id} - {self.user.email}"
    
    @property
    def is_active(self):
        now = timezone.now()
        return (
            self.status == "ACTIVE" and
            self.start_date <= now <= self.end_date
        )
    
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
        """Check if user can use this coupon."""
        from .models import Payment
        
        if not self.is_valid:
            return False
        
        # Check per-user usage limit
        user_usage = Payment.objects.filter(
            user=user,
            metadata__contains={"coupon_code": self.code}
        ).count()
        
        return user_usage < self.max_uses_per_user
