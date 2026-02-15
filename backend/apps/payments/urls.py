"""
Payments app URLs for Software Distribution Platform.

Stable webhook URL (used in Paystack dashboard):
https://yourdomain.com/api/v1/payments/webhook/paystack/
Do not change this path without coordinating with the Paystack configuration.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'payments', views.PaymentViewSet, basename='payment')
router.register(r'plans', views.PlanViewSet, basename='plan')
router.register(r'subscriptions', views.SubscriptionViewSet, basename='subscription')
router.register(r'invoices', views.InvoiceViewSet, basename='invoice')
router.register(r'coupons', views.CouponViewSet, basename='coupon')

urlpatterns = [
    path('', include(router.urls)),
    path('create-payment/', views.CreatePaymentView.as_view(), name='create-payment'),
    path('process-offline/', views.ProcessOfflinePaymentView.as_view(), name='process-offline'),
    path('verify-offline/<uuid:payment_id>/', views.VerifyOfflinePaymentView.as_view(), name='verify-offline'),
    path('webhook/stripe/', views.StripeWebhookView.as_view(), name='stripe-webhook'),
    path('webhook/paypal/', views.PayPalWebhookView.as_view(), name='paypal-webhook'),
    path('my-transactions/', views.UserTransactionsView.as_view(), name='user-transactions'),
]