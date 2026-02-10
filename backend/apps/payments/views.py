from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response

# AUTO-GENERATED PLACEHOLDERS (safe to replace later)

class PaymentViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({'status': 'PaymentViewSet placeholder'})


class InvoiceViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({'status': 'InvoiceViewSet placeholder'})


class SubscriptionViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({'status': 'SubscriptionViewSet placeholder'})


class CouponViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({'status': 'CouponViewSet placeholder'})


# --- APIViews ---
class CreatePaymentView(APIView):
    def post(self, request):
        return Response({'status': 'CreatePaymentView placeholder'})


class ProcessOfflinePaymentView(APIView):
    def post(self, request):
        return Response({'status': 'ProcessOfflinePaymentView placeholder'})


class VerifyOfflinePaymentView(APIView):
    def post(self, request, payment_id=None):
        return Response({'status': f'VerifyOfflinePaymentView placeholder for {payment_id}'})


class StripeWebhookView(APIView):
    def post(self, request):
        return Response({'status': 'StripeWebhookView placeholder'})


class PayPalWebhookView(APIView):
    def post(self, request):
        return Response({'status': 'PayPalWebhookView placeholder'})


class UserTransactionsView(APIView):
    def get(self, request):
        return Response({'status': 'UserTransactionsView placeholder'})
