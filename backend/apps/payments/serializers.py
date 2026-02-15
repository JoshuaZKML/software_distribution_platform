from rest_framework import serializers
from .models import Payment, Plan, Subscription, Invoice

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