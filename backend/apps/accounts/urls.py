# FILE: /backend/apps/accounts/urls.py (UPDATED - Added Unsubscribe URL)
from django.urls import path, include
from rest_framework import routers
from rest_framework_simplejwt.views import TokenVerifyView

from .views import (
    UserViewSet,
    AdminProfileViewSet,
    UserSessionViewSet,
    AdminActionLogViewSet,
    UserRegistrationView,
    VerifyEmailView,
    UserLoginView,
    UserLogoutView,
    CustomTokenRefreshView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    ChangePasswordView,
    # ===== NEW: Emergency 2FA views =====
    EmergencyTwoFactorSetupView,
    EmergencyTwoFactorVerifyView,
    RegenerateBackupCodesView,
    # ===== NEW: Device verification & management views =====
    DeviceVerificationConfirmView,
    DeviceManagementView,
    # ===== NEW: Unsubscribe view (added 2026‑02‑13) =====
    unsubscribe,
)

router = routers.DefaultRouter()

# Must give unique basenames because multiple ViewSets use the same User model
router.register(r'users', UserViewSet, basename='user')
router.register(r'admin-profiles', AdminProfileViewSet, basename='admin-profile')
router.register(r'sessions', UserSessionViewSet, basename='session')
router.register(r'actions', AdminActionLogViewSet, basename='action')

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),

    # Auth / Registration URLs
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('verify-email/<str:token>/', VerifyEmailView.as_view(), name='verify-email'),

    # Authentication endpoints
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # Password management endpoints
    path('reset-password/', PasswordResetRequestView.as_view(), name='reset-password'),
    path('reset-password/confirm/', PasswordResetConfirmView.as_view(), name='reset-password-confirm'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),

    # ===== NEW: Unsubscribe endpoint =====
    path('unsubscribe/', unsubscribe, name='unsubscribe'),

    # ===== NEW: Emergency 2FA endpoints =====
    path('2fa/emergency/setup/', EmergencyTwoFactorSetupView.as_view(), name='emergency-2fa-setup'),
    path('2fa/emergency/verify/', EmergencyTwoFactorVerifyView.as_view(), name='emergency-2fa-verify'),
    path('2fa/emergency/regenerate-backup-codes/', RegenerateBackupCodesView.as_view(), name='regenerate-backup-codes'),

    # ===== NEW: Device verification & management endpoints =====
    path('device/verify/confirm/', DeviceVerificationConfirmView.as_view(), name='device-verify-confirm'),
    path('devices/', DeviceManagementView.as_view(), name='device-management'),
    path('devices/<uuid:session_id>/', DeviceManagementView.as_view(), name='device-management-detail'),
]