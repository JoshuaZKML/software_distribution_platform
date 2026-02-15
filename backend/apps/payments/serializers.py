from rest_framework import serializers
from .models import Payment, Plan, Subscription, Invoice, Coupon, OfflinePayment  # <-- Coupon added
from decimal import Decimal  # added for Decimal min_value fix

# 👇 ADD THESE TWO IMPORTS (drf-spectacular type hints)
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes


# Placeholder serializers for APIViews (for schema generation only)
class GenericResponseSerializer(serializers.Serializer):
    """Generic response serializer for placeholder endpoints."""
    status = serializers.CharField(help_text="Status message")


class PaymentPlaceholderSerializer(serializers.Serializer):
    """Placeholder for Payment operations."""
    status = serializers.CharField()


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'amount', 'currency', 'status', 'payment_method',
            'gateway', 'gateway_reference', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_detail = PlanSerializer(source='plan', read_only=True)
    # Map legacy/API field names to actual model fields
    started_at = serializers.DateTimeField(source='start_date', read_only=True)
    canceled_at = serializers.DateTimeField(source='cancelled_at', read_only=True, allow_null=True)
    gateway = serializers.CharField(source='payment_method', read_only=True, allow_null=True)
    gateway_subscription_id = serializers.CharField(source='payment_gateway_id', read_only=True, allow_null=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'user', 'plan', 'plan_detail', 'status',
            'started_at', 'current_period_start', 'current_period_end',
            'canceled_at', 'ended_at', 'cancel_at_period_end',
            'gateway', 'gateway_subscription_id', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'created_at', 'updated_at',
            'started_at', 'current_period_start', 'current_period_end'  # set by system
        ]

    def validate(self, data):
        # Users cannot set status directly except via webhooks; we restrict creation.
        request = self.context.get('request')
        if request and request.method == 'POST':
            # Prevent client from setting arbitrary fields on creation.
            # Subscriptions should be created via payment webhook.
            raise serializers.ValidationError(
                "Subscriptions cannot be created directly. Please complete payment first."
            )
        return data


class InvoiceSerializer(serializers.ModelSerializer):
    # Map legacy/external field names to current model fields to keep
    # response structure stable while matching the model for schema gen.
    user = serializers.SerializerMethodField(read_only=True)
    number = serializers.CharField(source='invoice_number', read_only=True)
    tax = serializers.DecimalField(source='tax_amount', max_digits=10, decimal_places=2, read_only=True)
    amount = serializers.DecimalField(source='total', max_digits=10, decimal_places=2, read_only=True)
    due_at = serializers.DateTimeField(source='issued_at', read_only=True)
    metadata = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'user', 'payment', 'number',
            'status', 'currency', 'amount', 'tax', 'total',
            'issued_at', 'paid_at', 'due_at', 'pdf_file', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'number', 'status', 'issued_at', 'paid_at',
            'created_at', 'updated_at', 'pdf_file'
        ]

    def validate(self, data):
        # Additional validation for write operations if needed
        if self.instance and self.instance.status in ['issued', 'paid', 'void']:
            raise serializers.ValidationError("Cannot modify issued, paid, or void invoices.")
        return data

    # 👇 ADDED @extend_schema_field DECORATOR
    @extend_schema_field(OpenApiTypes.STR)
    def get_user(self, obj):
        try:
            return str(obj.payment.user.id) if obj and obj.payment and obj.payment.user else None
        except Exception:
            return None

    # 👇 ADDED @extend_schema_field DECORATOR
    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_metadata(self, obj):
        # Preserve an external 'metadata' key while mapping to model's notes
        return {'notes': obj.notes} if obj and getattr(obj, 'notes', None) else {}


# =============================================================================
# NEW SERIALIZERS – added without modifying existing code
# =============================================================================

class CouponSerializer(serializers.ModelSerializer):
    """Admin CRUD for coupons."""
    class Meta:
        model = Coupon  # Now defined because Coupon is imported
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'times_used']


class OfflinePaymentRequestSerializer(serializers.Serializer):
    """
    Validate and prepare an offline payment request.
    Expected fields vary by payment method.
    """
    software_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))  # fixed min_value to Decimal
    currency = serializers.CharField(max_length=3, required=False)
    payment_method = serializers.ChoiceField(
        choices=[
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('BANK_DEPOSIT', 'Bank Deposit'),
            ('CRYPTO', 'Crypto')
        ],
        default='BANK_TRANSFER'
    )
    # Optional fields for bank methods
    bank_name = serializers.CharField(required=False, allow_blank=True)
    account_name = serializers.CharField(required=False, allow_blank=True)
    account_number = serializers.CharField(required=False, allow_blank=True)
    reference_number = serializers.CharField(required=False, allow_blank=True)
    # Optional fields for crypto
    crypto_address = serializers.CharField(required=False, allow_blank=True)
    crypto_currency = serializers.CharField(required=False, allow_blank=True)
    # Additional metadata (e.g., receipt image, user notes)
    metadata = serializers.JSONField(default=dict, required=False)

    def validate_software_id(self, value):
        """
        Ensure the software exists and is active.
        Store the instance in context for later use.
        """
        from apps.products.models import Software  # lazy import to avoid circular deps
        try:
            software = Software.objects.get(id=value, is_active=True)
        except Software.DoesNotExist:
            raise serializers.ValidationError("Software not found or inactive.")
        self.context['software'] = software
        return value

    def validate(self, attrs):
        method = attrs.get('payment_method')
        if method in ('BANK_TRANSFER', 'BANK_DEPOSIT'):
            if not attrs.get('account_number'):
                raise serializers.ValidationError("Account number is required for bank transfers/deposits.")
            # bank_name is optional – many users may not know it, but we require at least one identifier
        elif method == 'CRYPTO':
            if not attrs.get('crypto_address'):
                raise serializers.ValidationError("Crypto address is required.")
        return attrs


class VerifyOfflinePaymentSerializer(serializers.Serializer):
    """Admin decision on an offline payment."""
    approved = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# ===== NEW: Transaction Serializer for User Transactions View =====
class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for user transaction history, including invoice details."""
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True, default=None)
    invoice_id = serializers.UUIDField(source='invoice.id', read_only=True, default=None)

    class Meta:
        model = Payment
        fields = [
            'id', 'amount', 'currency', 'status', 'created_at',
            'invoice_number', 'invoice_id'
        ]
        # All fields are read‑only for this view
        read_only_fields = fields
# =================================================================