"""
Licenses app URLs for Software Distribution Platform.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'activation-codes', views.ActivationCodeViewSet, basename='activationcode')
router.register(r'batches', views.CodeBatchViewSet, basename='codebatch')
router.register(r'features', views.LicenseFeatureViewSet, basename='licensefeature')
router.register(r'logs', views.ActivationLogViewSet, basename='activationlog')
# --- NEW: License usage tracking endpoint ---
router.register(r'usage', views.LicenseUsageViewSet, basename='license-usage')

urlpatterns = [
    path('', include(router.urls)),
    path('generate/', views.GenerateActivationCodeView.as_view(), name='generate-code'),
    path('validate/', views.ValidateActivationCodeView.as_view(), name='validate-code'),
    path('activate/', views.ActivateLicenseView.as_view(), name='activate-license'),
    path('deactivate/', views.DeactivateLicenseView.as_view(), name='deactivate-license'),
    path('revoke/<uuid:code_id>/', views.RevokeLicenseView.as_view(), name='revoke-license'),
    # --- NEW: POST‑only revocation without ID (uses request body) ---
    path('revoke/', views.RevokeLicenseView.as_view(), name='revoke-license-post'),
    path('my-licenses/', views.UserLicensesView.as_view(), name='user-licenses'),
    path('check-updates/<slug:software_slug>/', views.CheckForUpdatesView.as_view(), name='check-updates'),
    # --- NEW: Offline license file validation ---
    path('validate-offline/', views.validate_offline_license, name='validate-offline-license'),
]