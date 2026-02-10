"""
Security app URLs for Software Distribution Platform.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'abuse-attempts', views.AbuseAttemptViewSet, basename='abuseattempt')
router.register(r'alerts', views.AbuseAlertViewSet, basename='abusealert')
router.register(r'ip-blacklist', views.IPBlacklistViewSet, basename='ipblacklist')
router.register(r'code-blacklist', views.CodeBlacklistViewSet, basename='codeblacklist')

urlpatterns = [
    path('', include(router.urls)),
    path('settings/', views.SecuritySettingsView.as_view(), name='security-settings'),
    path('device-check/', views.DeviceFingerprintCheckView.as_view(), name='device-check'),
    path('suspicious-activity/', views.SuspiciousActivityReportView.as_view(), name='suspicious-activity'),
    path('audit-log/', views.AuditLogView.as_view(), name='audit-log'),
]
