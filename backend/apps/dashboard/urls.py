"""
Dashboard app URLs for Software Distribution Platform.
"""
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('overview/', views.DashboardOverviewView.as_view(), name='dashboard-overview'),
    path('analytics/', views.AnalyticsView.as_view(), name='analytics'),
    path('reports/', views.ReportsView.as_view(), name='reports'),
    path('user-activity/', views.UserActivityView.as_view(), name='user-activity'),
    path('sales/', views.SalesDashboardView.as_view(), name='sales-dashboard'),
    path('license-usage/', views.LicenseUsageDashboardView.as_view(), name='license-usage'),
    path('system-monitoring/', views.SystemMonitoringView.as_view(), name='system-monitoring'),
    # New: dashboard statistics endpoint
    path('stats/', views.DashboardStatsView.as_view(), name='dashboard-stats'),
]