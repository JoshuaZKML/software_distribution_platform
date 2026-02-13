# FILE: backend/apps/notifications/urls.py
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Tracking endpoints (public)
    path('track/open/<uuid:tracking_id>/', views.track_open, name='track-open'),
    path('track/click/<uuid:tracking_id>/', views.track_click, name='track-click'),

    # In‑App notification API (authenticated)
    path('api/notifications/', views.NotificationListView.as_view(), name='notification-list'),
    path('api/notifications/<uuid:pk>/', views.NotificationDetailView.as_view(), name='notification-detail'),
]