# FILE: backend/apps/analytics/urls.py
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # List all daily aggregates (most recent first). Supports filtering and ordering via query params.
    path('daily/', views.DailyAggregateListView.as_view(), name='daily-list'),
    # Retrieve a single daily aggregate by its UUID primary key.
    path('daily/<uuid:pk>/', views.DailyAggregateDetailView.as_view(), name='daily-detail'),
    # Optionally, add a date‑based lookup: path('daily/<str:date>/', ...)
]