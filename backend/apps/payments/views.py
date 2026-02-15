"""
Payments views for Software Distribution Platform.
"""
from drf_spectacular.utils import extend_schema 
import hashlib
import hmac
import json
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import serializers, status, viewsets, generics   # <-- added generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Coupon,
    CouponUsage,
    GatewayEventLog,
    Invoice,
    OfflinePayment,
    Payment,
    Plan,                # added for PlanViewSet
    Subscription,
)
from .serializers import (   # added serializers
    PaymentSerializer,
    PlanSerializer,
    SubscriptionSerializer,
    InvoiceSerializer,
    GenericResponseSerializer,
    PaymentPlaceholderSerializer,
    CouponSerializer,               # <-- new
    OfflinePaymentRequestSerializer, # <-- new
    TransactionSerializer,           # <-- new for user transactions
)

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# VIEWSETS – enhanced implementations (non‑disruptive replacements)
# ----------------------------------------------------------------------

class PaymentViewSet(viewsets.ViewSet):
    """
    Placeholder for Payment CRUD operations.
    Replace with actual implementation when ready.
    """
    serializer_class = PaymentPlaceholderSerializer
    def list(self, request):
        return Response({'status': 'PaymentViewSet placeholder'})


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and retrieve available subscription plans.
    (New view, added without disruption)
    """
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'code'   # allow lookup by code (e.g., /plans/pro_monthly/)


class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    CRUD for subscriptions. Only admins can list all; users can view their own.
    Creation is disabled via serializer validation; use webhooks.
    """
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # During schema generation, avoid accessing request.user
        if getattr(self, "swagger_fake_view", False):
            return Subscription.objects.none()

        user = self.request.user
        if user.is_staff:
            return Subscription.objects.all()
        return Subscription.objects.filter(user=user)

    def perform_create(self, serializer):
        # Disable creation – should be done via webhook.
        self.permission_denied(self.request, message="Direct subscription creation is not allowed.")

    def perform_update(self, serializer):
        # Only allow status updates via webhooks, not client.
        self.permission_denied(self.request, message="Subscription updates must be processed via payment gateway.")

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def webhook(self, request):
        """
        Endpoint for payment gateway webhooks to create/update subscriptions.
        Implement idempotency key handling and signature verification.
        """
        # Placeholder – real implementation would verify signature and update accordingly.
        return Response({"detail": "Webhook received"}, status=status.HTTP_200_OK)
    
    # ... (inside SubscriptionViewSet, after other actions)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        """
        Cancel a subscription.
        - If `immediate=true` is passed, cancel immediately (ends now).
        - Otherwise, sets `cancel_at_period_end=true` (cancels at end of current period).
        Only the subscription owner or an admin can cancel.
        """
        subscription = self.get_object()  # already filtered by get_queryset

        # Permission: only owner or admin
        if not (request.user.is_staff or subscription.user == request.user):
            return Response(
                {"detail": "You do not have permission to cancel this subscription."},
                status=status.HTTP_403_FORBIDDEN
            )

        immediate = request.data.get('immediate', False)
        if immediate:
            # Immediate cancellation
            subscription.cancel(immediate=True)
            message = "Subscription cancelled immediately."
        else:
            # Cancel at period end
            if subscription.cancel_at_period_end:
                return Response(
                    {"detail": "Subscription is already set to cancel at period end."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            subscription.cancel_at_period_end = True
            subscription.save(update_fields=['cancel_at_period_end'])
            message = "Subscription will be cancelled at the end of the current billing period."

        return Response({
            "success": True,
            "message": message,
            "subscription_id": str(subscription.id),
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "status": subscription.status,
            "ended_at": subscription.ended_at
        }, status=status.HTTP_200_OK)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read‑only invoices. Users can view their own; admins view all.
    PDF download added as a custom action.
    """
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # During schema generation, avoid accessing request.user
        if getattr(self, "swagger_fake_view", False):
            return Invoice.objects.none()

        user = self.request.user
        # Optimise by selecting related payment to avoid N+1 when accessing payment.user
        qs = Invoice.objects.select_related('payment').all()
        if user.is_staff:
            return qs
        # Filter via payment.user because Invoice does not have a direct user FK
        return qs.filter(payment__user=user)

    @action(detail=True, methods=['get'], url_path='download')
    def download_pdf(self, request, pk=None):
        """
        Serve the invoice PDF securely.
        """
        invoice = self.get_object()
        if not invoice.pdf_file:
            return Response({"detail": "PDF not available."}, status=status.HTTP_404_NOT_FOUND)

        # Use a secure file serving method (e.g., X-Accel-Redirect, signed S3 URL)
        try:
            file_url = invoice.pdf_file.url  # signed URL if AWS_QUERYSTRING_AUTH=True
            return Response({"download_url": file_url})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== NEW: Coupon CRUD (replaces placeholder) =====
class CouponViewSet(viewsets.ModelViewSet):
    """
    CRUD for coupons. Admin only.
    """
    queryset = Coupon.objects.all().order_by('-created_at')
    serializer_class = CouponSerializer
    permission_classes = [IsAuthenticated]  # IsAdminUser enforced in permissions; we'll override get_queryset for safety
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'discount_type']
    search_fields = ['code', 'description']
    ordering_fields = ['created_at', 'valid_from', 'valid_until']

    def get_queryset(self):
        # Ensure only admins can access any coupon
        if not self.request.user.is_staff:
            return Coupon.objects.none()
        return super().get_queryset()

    def perform_create(self, serializer):
        # Optionally set created_by if your model has that field
        serializer.save()
# ====================================================


# ----------------------------------------------------------------------
# PAYMENT INITIALISATION & PROCESSING
# ----------------------------------------------------------------------

class CreatePaymentView(APIView):
    """
    Placeholder for generic payment creation.
    Will be replaced with actual gateway integration.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = GenericResponseSerializer

    def post(self, request):
        return Response({'status': 'CreatePaymentView placeholder'})


# ===== NEW: Process Offline Payment =====
@extend_schema(exclude=True)
class ProcessOfflinePaymentView(APIView):
    """
    Initiate an offline payment (bank transfer, deposit, crypto).
    Creates a PENDING Payment and an associated OfflinePayment record.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OfflinePaymentRequestSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        software = data['software']
        amount = data['amount']
        currency = data.get('currency', software.currency)
        payment_method = data.get('payment_method', 'BANK_TRANSFER')
        metadata = data.get('metadata', {})

        with transaction.atomic():
            # Prevent duplicate pending offline payments for same user/software
            existing = Payment.objects.filter(
                user=request.user,
                software=software,
                payment_method__startswith='OFFLINE_',
                status=Payment.Status.PENDING
            ).exists()
            if existing:
                return Response(
                    {'error': 'You already have a pending offline payment for this software.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create Payment
            payment = Payment.objects.create(
                user=request.user,
                software=software,
                amount=amount,
                currency=currency,
                payment_method=f"OFFLINE_{payment_method}",
                status=Payment.Status.PENDING,
                metadata=metadata
            )
            # Create OfflinePayment
            offline = OfflinePayment.objects.create(
                payment=payment,
                status='PENDING',
                bank_name=data.get('bank_name', ''),
                account_name=data.get('account_name', ''),
                account_number=data.get('account_number', ''),
                reference_number=data.get('reference_number', ''),
                crypto_address=data.get('crypto_address', ''),
                crypto_currency=data.get('crypto_currency', '')
            )
            # Optionally send email with instructions (implement separately if needed)

        # Return dynamic instructions based on payment method
        instructions = {
            'BANK_TRANSFER': "Please transfer the amount to the bank account provided in your dashboard and upload the receipt.",
            'CRYPTO': f"Send {amount} {currency} to the following crypto address: {offline.crypto_address or 'check dashboard'}.",
        }.get(payment_method, "Please complete the payment using the instructions in your dashboard.")

        return Response({
            'payment_id': str(payment.id),
            'offline_payment_id': str(offline.id),
            'instructions': instructions,
            'status': 'pending'
        }, status=status.HTTP_201_CREATED)
# ========================================


# ===== NEW: Verify Offline Payment =====
@extend_schema(exclude=True)
class VerifyOfflinePaymentView(APIView):
    """
    Admin view to manually verify an offline payment receipt.
    Updates OfflinePayment status and, if completed, marks Payment as SUCCESS.
    """
    permission_classes = [IsAuthenticated]  # We'll enforce staff manually

    def post(self, request, payment_id=None):
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('status')
        if new_status not in ['COMPLETED', 'REJECTED']:
            return Response({'error': 'Invalid status. Use COMPLETED or REJECTED.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            offline = OfflinePayment.objects.select_related('payment').get(payment_id=payment_id)
        except OfflinePayment.DoesNotExist:
            return Response({'error': 'Offline payment not found'}, status=status.HTTP_404_NOT_FOUND)

        if offline.status != 'PENDING':
            return Response({'error': f'Offline payment already {offline.status}'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            offline.status = new_status
            offline.save(update_fields=['status'])

            if new_status == 'COMPLETED':
                offline.payment.status = Payment.Status.SUCCESS
                offline.payment.save(update_fields=['status'])
                # Optionally create invoice, grant access, etc.

        return Response({
            'offline_payment_id': str(offline.id),
            'status': offline.status,
            'payment_status': offline.payment.status
        }, status=status.HTTP_200_OK)
# ========================================


# ===== NEW: User Transactions View (replaces placeholder) =====
class UserTransactionsView(generics.ListAPIView):
    """
    List all payments and invoices for the authenticated user.
    Pagination is handled automatically via DRF settings.
    """
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Avoid accessing request.user during schema generation
        if getattr(self, "swagger_fake_view", False):
            return Payment.objects.none()
        # Return payments for the current user, ordered newest first.
        # The serializer will include invoice details via source fields.
        return Payment.objects.filter(user=self.request.user).order_by('-created_at')
# ============================================================


# ----------------------------------------------------------------------
# PAYMENT GATEWAY WEBHOOKS – placeholders ready for extension
# ----------------------------------------------------------------------

@extend_schema(exclude=True)
class StripeWebhookView(APIView):
    """
    Webhook endpoint for Stripe events.
    - Returns 200 immediately to acknowledge receipt.
    - Logs the raw request (truncated) for debugging.
    - TODO: implement signature verification using Stripe-Signature header.
    - TODO: add idempotency key / event_id tracking to prevent duplicate processing.
    - TODO: dispatch events (e.g., payment_intent.succeeded) to update Payment/Invoice.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Log truncated payload (mask sensitive data if needed)
        logger.info(f"Stripe webhook received (first 500 chars): {request.body[:500]}")
        
        # TODO: verify signature with stripe.Webhook.construct_event()
        # signature = request.headers.get('Stripe-Signature')
        # if not signature:
        #     return Response({'error': 'Missing signature'}, status=status.HTTP_400_BAD_REQUEST)
        # try:
        #     event = stripe.Webhook.construct_event(
        #         payload=request.body, sig_header=signature, secret=settings.STRIPE_WEBHOOK_SECRET
        #     )
        # except ValueError:
        #     return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)
        # except stripe.error.SignatureVerificationError:
        #     return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)
        #
        # TODO: check if event.id already processed (cache/table)
        # TODO: handle event types (e.g., 'payment_intent.succeeded')
        
        return Response({'status': 'received'}, status=status.HTTP_200_OK)


@extend_schema(exclude=True)
class PayPalWebhookView(APIView):
    """
    Webhook endpoint for PayPal events.
    - Returns 200 immediately to acknowledge receipt.
    - Logs the raw request (truncated) for debugging.
    - TODO: implement verification (e.g., validate webhook ID with PayPal API).
    - TODO: add idempotency key / transmission_id tracking.
    - TODO: dispatch events (e.g., PAYMENT.CAPTURE.COMPLETED) to update Payment/Invoice.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # Log truncated payload
        logger.info(f"PayPal webhook received (first 500 chars): {request.body[:500]}")
        
        # TODO: verify PayPal webhook signature
        # See: https://developer.paypal.com/docs/api/webhooks/v1/#verify-webhook-signature
        # - Extract headers: paypal-transmission-id, paypal-transmission-time, paypal-transmission-sig, etc.
        # - Call PayPal verification API with the event body and headers.
        #
        # if not verification_passed:
        #     return Response({'error': 'Verification failed'}, status=status.HTTP_400_BAD_REQUEST)
        #
        # TODO: deduplicate based on transmission_id
        # TODO: handle event types
        
        return Response({'status': 'received'}, status=status.HTTP_200_OK)


# ----------------------------------------------------------------------
# PAYSTACK INTEGRATION – unchanged (preserved in full)
# ----------------------------------------------------------------------

PAYSTACK_SUPPORTED_CURRENCIES = getattr(
    settings, 'PAYSTACK_SUPPORTED_CURRENCIES',
    ["NGN", "USD", "GHS", "ZAR", "KES"]
)

MAX_WEBHOOK_SIZE = getattr(settings, 'PAYSTACK_WEBHOOK_MAX_SIZE', 1024 * 100)  # 100KB default


class PaymentStatus:
    """Mirrors Payment.Status (avoid drift by using model choices where possible)."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"


def mask_sensitive_data(payload):
    """Remove sensitive fields from payload before logging."""
    if not isinstance(payload, dict):
        return payload
    masked = payload.copy()
    for key in ['email', 'customer', 'authorization', 'card']:
        if key in masked:
            masked[key] = '***REDACTED***'
    if 'data' in masked and isinstance(masked['data'], dict):
        masked['data'] = mask_sensitive_data(masked['data'])
    return masked


def send_payment_failed_email(payment):
    """
    Send a professional email to the user when a payment attempt fails.
    Suggests alternative payment methods (bank transfer, deposit, crypto).
    Can be disabled via settings.SEND_PAYMENT_FAILED_EMAIL = False.
    """
    if not getattr(settings, 'SEND_PAYMENT_FAILED_EMAIL', True):
        return

    # Prevent sending duplicate emails if payment is already marked failed
    if payment.status != PaymentStatus.FAILED:
        return

    subject = "Action Required: Your Payment Was Not Successful"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')

    # Plain text version (fallback and primary)
    message = f"""
Dear {payment.user.get_full_name() or payment.user.email},

We noticed that your recent payment for **{payment.software.name}** 
in the amount of **{payment.amount} {payment.currency}** was not successful.

This could be due to insufficient funds, card restrictions, or a temporary 
issue with your payment method.

You can complete your purchase using one of the following alternative 
payment methods:

• **Bank Transfer**: Make a direct transfer to our corporate bank account. 
  Please use your order number ({payment.id}) as reference and upload the 
  receipt in your dashboard.

• **Bank Deposit**: Deposit the exact amount at any branch of our partner 
  banks. Instructions are available after selecting this method.

• **Cryptocurrency (Bitcoin)**: Send the equivalent amount in Bitcoin to 
  the address provided in your dashboard.

To proceed, please visit your order dashboard or contact our support team 
at support@example.com.

We apologise for any inconvenience and are here to assist you.

Best regards,
The Software Distribution Platform Team
"""

    # HTML version – can be customised via templates if needed
    html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 10px; text-align: center; }}
        .footer {{ margin-top: 30px; font-size: 0.9em; color: #6c757d; }}
        ul {{ list-style-type: none; padding-left: 0; }}
        li {{ margin-bottom: 10px; padding-left: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Payment Issue – Alternative Methods Available</h2>
        </div>
        <p>Dear {payment.user.get_full_name() or payment.user.email},</p>
        <p>We noticed that your recent payment for <strong>{payment.software.name}</strong><br>
        in the amount of <strong>{payment.amount} {payment.currency}</strong> was not successful.</p>
        <p>This could be due to insufficient funds, card restrictions, or a temporary issue with your payment method.</p>
        <p><strong>You can complete your purchase using one of the following alternative payment methods:</strong></p>
        <ul>
            <li>✅ <strong>Bank Transfer</strong> – Direct transfer to our corporate bank account.<br>
                <small>Use order reference <code>{payment.id}</code> and upload the receipt in your dashboard.</small>
            </li>
            <li>✅ <strong>Bank Deposit</strong> – Deposit the exact amount at any branch of our partner banks.<br>
                <small>Instructions available after selecting this method.</small>
            </li>
            <li>✅ <strong>Cryptocurrency (Bitcoin)</strong> – Send the equivalent amount in Bitcoin.<br>
                <small>Address provided in your dashboard.</small>
            </li>
        </ul>
        <p>To proceed, please visit your <a href="{getattr(settings, 'SITE_URL', '#')}/dashboard">order dashboard</a> or contact our support team at <a href="mailto:support@example.com">support@example.com</a>.</p>
        <p>We apologise for any inconvenience and are here to assist you.</p>
        <p>Best regards,<br>The Software Distribution Platform Team</p>
        <div class="footer">
            <p>This is an automated message, please do not reply directly.</p>
        </div>
    </div>
</body>
</html>
"""

    try:
        send_mail(
            subject,
            message,
            from_email,
            [payment.user.email],
            html_message=html_message,
            fail_silently=True,
        )
        logger.info(f"Payment failure email sent to {payment.user.email} for payment {payment.id}")
    except Exception as e:
        logger.exception(f"Failed to send payment failure email: {e}")


class PaystackInitSerializer(serializers.Serializer):
    """Validate Paystack initialisation requests."""
    software_id = serializers.UUIDField()
    currency = serializers.ChoiceField(
        choices=PAYSTACK_SUPPORTED_CURRENCIES,
        default="NGN"
    )
    coupon_code = serializers.CharField(required=False, allow_blank=True)

    def validate_software_id(self, value):
        """Ensure the software exists and is purchasable."""
        Software = apps.get_model('products', 'Software')
        try:
            software = Software.objects.get(id=value, is_active=True)
        except Software.DoesNotExist:
            raise serializers.ValidationError("Software not found or not available.")
        self.context['software'] = software
        return value

    def validate(self, data):
        """Check that user has an email address."""
        request = self.context.get('request')
        if request and not request.user.email:
            raise serializers.ValidationError("User must have a verified email address.")
        return data


class InitializePaystackPaymentView(APIView):
    """
    Initialize a Paystack transaction.
    - Server‑side price calculation (client amount is ignored).
    - Coupon discount applied as Decimal (no float conversion).
    - Creates PENDING payment, then calls Paystack API.
    - Rolls back coupon usage if gateway call fails.
    - Verifies gateway response reference matches internal reference.
    - Sends email notification on payment failure.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1. Input validation
        serializer = PaystackInitSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        software = serializer.context['software']
        currency = serializer.validated_data['currency']
        coupon_code = serializer.validated_data.get('coupon_code')

        # 2. Verify that software price currency matches selected currency
        if software.currency != currency:
            return Response(
                {'error': f'Software is priced in {software.currency}, cannot pay in {currency}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Price and discount calculation (pure Decimal)
        base_price = software.price
        final_amount = base_price
        coupon = None
        discount_amount = Decimal('0.00')

        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code, is_active=True)
                if coupon.is_valid and coupon.can_be_used_by_v2(request.user):
                    discount_amount = coupon.calculate_discount(base_price)
                    final_amount = base_price - discount_amount
                else:
                    return Response(
                        {'coupon_error': 'Coupon is invalid or cannot be used by this user.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Coupon.DoesNotExist:
                return Response(
                    {'coupon_error': 'Coupon does not exist.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if final_amount < 0:
            final_amount = Decimal('0.00')

        # 4. Prevent duplicate pending payments – use row‑level locking to avoid race
        with transaction.atomic():
            # Lock the user row to prevent concurrent init for same user/software
            user = request.user.__class__.objects.select_for_update().get(pk=request.user.pk)
            existing_pending = Payment.objects.filter(
                user=user,
                software=software,
                payment_method="PAYSTACK",
                status=PaymentStatus.PENDING
            ).exists()
            if existing_pending:
                return Response(
                    {'error': 'You already have a pending payment for this software.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 5. Atomic creation of payment (coupon usage is recorded tentatively)
            payment = Payment.objects.create(
                user=user,
                software=software,
                amount=final_amount,
                currency=currency,
                payment_method="PAYSTACK",
                status=PaymentStatus.PENDING,
                metadata={
                    'base_price': str(base_price),
                    'discount': str(discount_amount),
                    'coupon_code': coupon_code if coupon else None,
                }
            )

            # Set transaction_id to internal UUID (will be used as Paystack reference)
            payment.transaction_id = str(payment.id)
            payment.metadata = {**(payment.metadata or {}), **payment.get_paystack_metadata()}
            payment.save(update_fields=['transaction_id', 'metadata'])

            # Tentatively record coupon usage (will be rolled back if gateway fails)
            if coupon and discount_amount > 0:
                coupon.apply_usage(request.user, payment=payment)

        # 6. Call Paystack API with robust retry logic
        try:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            session = requests.Session()
            retries = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504],
                allowed_methods=["POST"]
            )
            session.mount('https://', HTTPAdapter(max_retries=retries))

            paystack_url = "https://api.paystack.co/transaction/initialize"
            headers = {
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json",
            }
            domain_url = getattr(settings, 'DOMAIN_URL', None)
            if not domain_url:
                domain_url = f"{request.scheme}://{request.get_host()}"
                logger.warning("DOMAIN_URL not set; using dynamic host for callback URL (security risk).")

            payload = {
                "email": request.user.email,
                "amount": int((payment.amount.quantize(Decimal('0.01')) * 100)),
                "currency": payment.currency,
                "reference": payment.transaction_id,
                "metadata": payment.metadata,
                "callback_url": f"{domain_url}/payments/verify",
            }

            response = session.post(paystack_url, json=payload, headers=headers, timeout=15)
            try:
                res_data = response.json()
            except ValueError:
                raise Exception("Invalid JSON response from Paystack")

            if response.status_code == 200 and res_data.get('status'):
                returned_ref = res_data.get('data', {}).get('reference')
                if returned_ref != payment.transaction_id:
                    with transaction.atomic():
                        CouponUsage.objects.filter(payment=payment).delete()
                        payment.mark_failed(reason="Paystack reference mismatch")
                        send_payment_failed_email(payment)  # <-- Email notification
                    logger.error(f"Paystack reference mismatch: expected {payment.transaction_id}, got {returned_ref}")
                    return Response(
                        {'error': 'Payment gateway integrity error.'},
                        status=status.HTTP_502_BAD_GATEWAY
                    )

                return Response({
                    'payment_id': str(payment.id),
                    'authorization_url': res_data['data']['authorization_url'],
                    'access_code': res_data['data']['access_code'],
                    'reference': res_data['data']['reference'],
                }, status=status.HTTP_201_CREATED)
            else:
                error_msg = res_data.get('message', 'Unknown error')
                with transaction.atomic():
                    CouponUsage.objects.filter(payment=payment).delete()
                    payment.mark_failed(reason=f"Paystack init failed: {error_msg}")
                    send_payment_failed_email(payment)  # <-- Email notification
                logger.error(f"Paystack initialization error: {res_data}")
                return Response(
                    {'error': 'Payment gateway error, please try again.'},
                    status=status.HTTP_502_BAD_GATEWAY
                )

        except ImportError:
            logger.critical("requests library not installed – cannot initialize Paystack.")
            return Response(
                {'error': 'Payment service unavailable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.exception(f"Paystack API call failed: {str(e)}")
            with transaction.atomic():
                CouponUsage.objects.filter(payment=payment).delete()
                payment.mark_failed(reason="Paystack init network error")
                send_payment_failed_email(payment)  # <-- Email notification
            return Response(
                {'error': 'Payment gateway communication failed.'},
                status=status.HTTP_502_BAD_GATEWAY
            )


class PaystackBankTransferView(APIView):
    """
    Handle Paystack's "Pay with Bank Transfer" feature.
    Automated flow – webhook marks payment completed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Placeholder – extend with 'channels': ['bank_transfer'] in payload
        return Response({'status': 'PaystackBankTransferView placeholder'})


class PaystackWebhookThrottle(AnonRateThrottle):
    """Rate limit for unauthenticated webhook endpoints."""
    rate = getattr(settings, 'PAYSTACK_WEBHOOK_THROTTLE_RATE', '100/hour')


class PaystackWebhookView(APIView):
    """
    Enterprise‑grade Paystack webhook handler.
    - Signature verification using raw request body (mitigates hash flooding).
    - Content-Type and payload size checks.
    - IP allowlist **only safe when behind trusted proxy** – disabled by default.
    - Atomic transaction with row locking.
    - Idempotent – ignores already‑processed events.
    - Verifies amount (with tolerance), currency, and payment status.
    - Email mismatch logged but not rejected.
    - Calls Paystack verify endpoint with retry; does NOT fail payment on transient errors.
    - Stores raw and masked payloads; deduplicates log entries via unique hash.
    - Logs webhook AFTER processing with actual HTTP status code.
    - Sends email notification on payment failure.
    """
    permission_classes = [AllowAny]
    throttle_classes = [PaystackWebhookThrottle]

    # IP allowlist is disabled by default. To use, set PAYSTACK_WEBHOOK_ALLOWED_IPS in settings
    # and ensure you are behind a trusted proxy with proper configuration.
    ALLOWED_IPS = getattr(settings, 'PAYSTACK_WEBHOOK_ALLOWED_IPS', None)

    def _verify_ip(self, request) -> bool:
        """Restrict access to known IPs. Only safe with trusted proxy configuration."""
        if self.ALLOWED_IPS is None:
            return True
        # Use django-ipware in production; this is a simplified fallback.
        client_ip = request.META.get('REMOTE_ADDR')
        # If behind proxy, the IP should be set by middleware or load balancer.
        # We do NOT parse X-Forwarded-For directly – that's unsafe.
        return client_ip in self.ALLOWED_IPS

    def _verify_signature(self, raw_body: bytes, signature: str) -> bool:
        """Verify x-paystack-signature header using raw body (timing-safe)."""
        if not signature:
            return False
        secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
        expected = hmac.new(secret, raw_body, hashlib.sha512).hexdigest()
        return hmac.compare_digest(expected, signature)

    def _verify_with_gateway(self, reference: str) -> dict:
        """
        Call Paystack transaction verify endpoint with retry and backoff.
        Raises exception only after all retries fail (transient errors will be retried).
        """
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code >= 500:
            # Let webhook retry; do not raise here – we'll return None and let caller decide.
            return None
        response.raise_for_status()
        data = response.json()
        if not data.get('status'):
            raise Exception(f"Paystack verify returned error: {data.get('message')}")
        return data['data']

    def _mask_sensitive_data(self, payload):
        return mask_sensitive_data(payload)

    def post(self, request):
        # 0. Correlation ID for tracing
        correlation_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        logger.info(f"[{correlation_id}] Paystack webhook received")

        # 1. IP allowlist (if configured) – only safe with proper proxy setup.
        if not self._verify_ip(request):
            logger.warning(f"[{correlation_id}] Paystack webhook from unauthorised IP: {request.META.get('REMOTE_ADDR')}")
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        # 2. Content-Type check
        if request.content_type != 'application/json':
            logger.warning(f"[{correlation_id}] Paystack webhook with invalid content type: {request.content_type}")
            return Response({'error': 'Unsupported Media Type'}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

        # 3. Payload size limit
        raw_body = request.body
        if len(raw_body) > MAX_WEBHOOK_SIZE:
            logger.error(f"[{correlation_id}] Paystack webhook payload too large: {len(raw_body)} bytes")
            return Response({'error': 'Payload too large'}, status=status.HTTP_413_PAYLOAD_TOO_LARGE)

        # 4. Signature verification using raw body
        signature = request.headers.get('x-paystack-signature', '')
        if not self._verify_signature(raw_body, signature):
            self._log_event(
                event_type=None,
                reference=None,
                payload={},
                status_code=401,
                error='Invalid signature',
                raw_payload=raw_body,
                correlation_id=correlation_id
            )
            return Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)

        # 5. Parse JSON safely
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            self._log_event(
                event_type=None,
                reference=None,
                payload={},
                status_code=400,
                error='Invalid JSON',
                raw_payload=raw_body,
                correlation_id=correlation_id
            )
            return Response({'error': 'Invalid JSON'}, status=status.HTTP_400_BAD_REQUEST)

        event = payload.get('event')
        data = payload.get('data', {})

        # 6. Event type filtering
        if event not in ['charge.success', 'charge.failed']:
            logger.info(f"[{correlation_id}] Paystack webhook ignored: {event}")
            self._log_event(
                event_type=event,
                reference=data.get('reference'),
                payload=self._mask_sensitive_data(payload),
                status_code=200,
                raw_payload=raw_body,
                correlation_id=correlation_id
            )
            return Response({'status': 'ignored'})

        reference = data.get('reference')
        if not reference:
            self._log_event(
                event_type=event,
                reference=None,
                payload=self._mask_sensitive_data(payload),
                status_code=400,
                error='Missing reference',
                raw_payload=raw_body,
                correlation_id=correlation_id
            )
            return Response({'error': 'Missing reference'}, status=status.HTTP_400_BAD_REQUEST)

        # Initialize final status tracking for logging (will be updated before any return)
        final_status_code = 200
        final_error = None

        try:
            with transaction.atomic():
                # 7. Lookup payment by reference (requires unique transaction_id in DB)
                payment = Payment.objects.select_for_update().get(transaction_id=reference)

                # 8. Idempotency – skip if already finalised
                if payment.status in [PaymentStatus.COMPLETED, PaymentStatus.FAILED]:
                    logger.info(f"[{correlation_id}] Paystack webhook: payment {payment.id} already {payment.status}")
                    return Response({'status': 'already_processed'})

                # 9. Payment age check – only for PENDING payments, using expires_at if available
                if payment.status == PaymentStatus.PENDING:
                    expiry = getattr(payment, 'expires_at', payment.created_at + timedelta(hours=24))
                    if timezone.now() > expiry:
                        payment.mark_failed(reason="Webhook received after expiry")
                        send_payment_failed_email(payment)  # <-- Email notification
                        logger.error(f"[{correlation_id}] Paystack webhook: payment {payment.id} expired")
                        final_status_code = 400
                        final_error = "Payment expired"
                        return Response({'error': 'Payment expired'}, status=status.HTTP_400_BAD_REQUEST)

                # 10. Currency verification – strict
                charged_currency = data.get('currency')
                if charged_currency != payment.currency:
                    payment.mark_failed(reason=f"Currency mismatch: expected {payment.currency}, got {charged_currency}")
                    send_payment_failed_email(payment)  # <-- Email notification
                    logger.error(f"[{correlation_id}] Paystack webhook: currency mismatch for payment {payment.id}")
                    final_status_code = 400
                    final_error = "Currency mismatch"
                    return Response({'error': 'Currency mismatch'}, status=status.HTTP_400_BAD_REQUEST)

                # 11. Email verification – log mismatch but do NOT fail
                customer_email = data.get('customer', {}).get('email')
                if customer_email and customer_email != payment.user.email:
                    logger.warning(f"[{correlation_id}] Paystack webhook: email mismatch for payment {payment.id}. "
                                   f"Expected {payment.user.email}, got {customer_email}")
                    payment.status_reason = f"Email mismatch: {customer_email}"
                    payment.save(update_fields=['status_reason'])

                # 12. Amount verification with tolerance (allow 1 cent difference)
                if event == 'charge.success':
                    raw_amount = data.get('amount')
                    if raw_amount is None:
                        raise ValueError("Missing amount in webhook payload")
                    charged_amount = Decimal(str(raw_amount)) / 100
                    if abs(charged_amount - payment.amount) > Decimal('0.01'):
                        payment.mark_failed(
                            reason=f"Amount mismatch: expected {payment.amount}, got {charged_amount}"
                        )
                        send_payment_failed_email(payment)  # <-- Email notification
                        logger.error(f"[{correlation_id}] Paystack webhook: amount mismatch for payment {payment.id}")
                        final_status_code = 400
                        final_error = "Amount mismatch"
                        return Response({'error': 'Amount mismatch'}, status=status.HTTP_400_BAD_REQUEST)

                    # 13. Verify with Paystack API (defence in depth) – with retry, do NOT fail payment on transient error
                    verify_data = self._verify_with_gateway(reference)
                    if verify_data is None:
                        # Verification temporarily unavailable; return 500 to trigger webhook retry
                        logger.warning(f"[{correlation_id}] Paystack webhook: verification unavailable for payment {payment.id}, will retry")
                        final_status_code = 503
                        final_error = "Verification temporarily unavailable"
                        return Response(
                            {'error': 'Verification service unavailable, please retry'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE
                        )

                    # Verify transaction status and integrity
                    if verify_data.get('status') != 'success':
                        payment.mark_failed(reason=f"Gateway verify status: {verify_data.get('status')}")
                        send_payment_failed_email(payment)  # <-- Email notification
                        logger.error(f"[{correlation_id}] Paystack webhook: verification failed for payment {payment.id}")
                        final_status_code = 400
                        final_error = "Verification failed"
                        return Response({'error': 'Verification failed'}, status=status.HTTP_400_BAD_REQUEST)

                    # Additional consistency checks
                    if Decimal(str(verify_data.get('amount', 0))) / 100 != payment.amount:
                        logger.error(f"[{correlation_id}] Paystack webhook: verified amount mismatch for payment {payment.id}")
                        # Do NOT mark failed – log only, discrepancy may be due to rounding
                    if verify_data.get('currency') != payment.currency:
                        logger.error(f"[{correlation_id}] Paystack webhook: verified currency mismatch for payment {payment.id}")

                    # 14. Verify that data['status'] == 'success'
                    if data.get('status') != 'success':
                        payment.mark_failed(reason=f"Unexpected charge status: {data.get('status')}")
                        send_payment_failed_email(payment)  # <-- Email notification
                        logger.error(f"[{correlation_id}] Paystack webhook: charge status is not success for payment {payment.id}")
                        final_status_code = 400
                        final_error = "Charge not successful"
                        return Response({'error': 'Charge not successful'}, status=status.HTTP_400_BAD_REQUEST)

                # 15. Process event
                if event == 'charge.success':
                    # Safely update metadata
                    new_metadata = {**(payment.metadata or {})}
                    new_metadata['paystack_charge_id'] = data.get('id')
                    new_metadata['paystack_transaction_date'] = data.get('transaction_date')
                    payment.metadata = new_metadata
                    payment.save(update_fields=['metadata'])

                    payment.mark_completed(
                        transaction_id=reference,
                        gateway_reference=reference
                    )
                    logger.info(f"[{correlation_id}] Paystack payment completed: {payment.id}, ref: {reference}")

                elif event == 'charge.failed':
                    failure_message = data.get('gateway_response', 'Payment failed')
                    payment.mark_failed(reason=f"Paystack: {failure_message}")
                    send_payment_failed_email(payment)  # <-- Email notification
                    logger.info(f"[{correlation_id}] Paystack payment failed: {payment.id}, ref: {reference}")

        except Payment.DoesNotExist:
            final_status_code = 404
            final_error = f"Payment with transaction_id={reference} not found"
            logger.error(f"[{correlation_id}] Paystack webhook: {final_error}")
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        except Payment.MultipleObjectsReturned:
            final_status_code = 409
            final_error = f"Multiple payments with transaction_id={reference}"
            logger.error(f"[{correlation_id}] Paystack webhook: {final_error}. DB uniqueness required.")
            return Response({'error': 'Duplicate transaction ID'}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            final_status_code = 500
            final_error = str(e)
            logger.exception(f"[{correlation_id}] Paystack webhook error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            # 16. Log event AFTER processing with final outcome
            self._log_event(
                event_type=event,
                reference=reference,
                payload=self._mask_sensitive_data(payload),
                status_code=final_status_code,
                error=final_error,
                raw_payload=raw_body,
                correlation_id=correlation_id
            )

        return Response({'status': 'success'}, status=status.HTTP_200_OK)

    def _log_event(self, event_type, reference, payload, status_code, error=None, raw_payload=None, correlation_id=None):
        """Create immutable audit log of webhook event with deduplication."""
        try:
            # Generate payload hash for deduplication (unique constraint on DB)
            payload_hash = hashlib.sha256(raw_payload).hexdigest() if raw_payload else None
            GatewayEventLog.objects.create(
                gateway='paystack',
                event_type=event_type,
                reference=reference,
                payload=payload,          # Masked parsed payload
                raw_payload=raw_payload,  # Raw bytes for forensic replay
                status_code=status_code,
                error_message=str(error) if error else '',
                correlation_id=correlation_id,
                payload_hash=payload_hash,
            )
        except IntegrityError:
            # Duplicate event – ignore (already logged)
            logger.debug(f"Duplicate webhook event detected: {payload_hash}")
        except Exception as e:
            logger.exception(f"Failed to log Paystack webhook: {e}")