"""
Main API endpoints for Software Distribution Platform.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Public endpoints
    path('status/', views.APIStatusView.as_view(), name='api-status'),
    path('catalog/', views.PublicCatalogView.as_view(), name='public-catalog'),
    
    # System endpoints
    path('system/health/', views.SystemHealthView.as_view(), name='system-health'),
    path('system/metrics/', views.SystemMetricsView.as_view(), name='system-metrics'),
    path('system/config/', views.SystemConfigView.as_view(), name='system-config'),
]
