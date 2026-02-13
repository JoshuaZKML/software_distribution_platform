"""
Payments views for Software Distribution Platform.
"""
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
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import (
    Coupon,
    CouponUsage,
    GatewayEventLog,
    Invoice,
    OfflinePayment,
    Payment,
    Subscription,
)

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# VIEWSETS – kept as placeholders (no disruption to existing workflows)
# ----------------------------------------------------------------------

class PaymentViewSet(viewsets.ViewSet):
    """
    Placeholder for Payment CRUD operations.
    Replace with actual implementation when ready.
    """
    def list(self, request):
        return Response({'status': 'PaymentViewSet placeholder'})


class InvoiceViewSet(viewsets.ViewSet):
    """
    Placeholder for Invoice CRUD operations.
    """
    def list(self, request):
        return Response({'status': 'InvoiceViewSet placeholder'})


class SubscriptionViewSet(viewsets.ViewSet):
    """
    Placeholder for Subscription CRUD operations.
    """
    def list(self, request):
        return Response({'status': 'SubscriptionViewSet placeholder'})


class CouponViewSet(viewsets.ViewSet):
    """
    Placeholder for Coupon CRUD operations.
    """
    def list(self, request):
        return Response({'status': 'CouponViewSet placeholder'})


# ----------------------------------------------------------------------
# PAYMENT INITIALISATION & PROCESSING (existing placeholders preserved)
# ----------------------------------------------------------------------

class CreatePaymentView(APIView):
    """
    Placeholder for generic payment creation.
    Will be replaced with actual gateway integration.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'status': 'CreatePaymentView placeholder'})


class ProcessOfflinePaymentView(APIView):
    """
    Placeholder for initiating an offline payment (bank transfer).
    Creates an OfflinePayment record linked to a Payment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response({'status': 'ProcessOfflinePaymentView placeholder'})


class VerifyOfflinePaymentView(APIView):
    """
    Placeholder for manual verification of offline payment receipts.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id=None):
        return Response({'status': f'VerifyOfflinePaymentView placeholder for {payment_id}'})


class UserTransactionsView(APIView):
    """
    Placeholder for retrieving authenticated user's payment history.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'status': 'UserTransactionsView placeholder'})


# ----------------------------------------------------------------------
# PAYMENT GATEWAY WEBHOOKS – existing placeholders kept
# ----------------------------------------------------------------------

class StripeWebhookView(APIView):
    """
    Placeholder for Stripe webhook endpoint.
    Should be replaced with actual webhook verification and payment completion.
    """
    permission_classes = [AllowAny]  # Webhooks are external calls

    def post(self, request):
        return Response({'status': 'StripeWebhookView placeholder'})


class PayPalWebhookView(APIView):
    """
    Placeholder for PayPal webhook endpoint.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        return Response({'status': 'PayPalWebhookView placeholder'})


# ----------------------------------------------------------------------
# PAYSTACK INTEGRATION – FINANCIAL‑GRADE HARDENING
# All changes are non‑disruptive; existing placeholders untouched.
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


# ----------------------------------------------------------------------
# EMAIL NOTIFICATION ON PAYMENT FAILURE (non‑disruptive addition)
# ----------------------------------------------------------------------

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
