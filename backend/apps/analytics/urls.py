# FILE: backend/apps/analytics/urls.py
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Existing daily aggregate endpoints
    path('daily/', views.DailyAggregateListView.as_view(), name='daily-list'),
    path('daily/<uuid:pk>/', views.DailyAggregateDetailView.as_view(), name='daily-detail'),
    # Optionally, add a date‑based lookup: path('daily/<str:date>/', ...)

    # Export job endpoints
    path('exports/', views.ExportJobListView.as_view(), name='export-list'),
    path('exports/<uuid:pk>/', views.ExportJobDetailView.as_view(), name='export-detail'),
    path('exports/<uuid:pk>/download/', views.ExportJobDownloadView.as_view(), name='export-download'),

    # New cohort endpoints
    path('cohorts/', views.CohortAggregateListView.as_view(), name='cohort-list'),
]