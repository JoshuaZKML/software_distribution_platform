# FILE: backend/apps/distribution/urls.py
from django.urls import path
from . import views

app_name = 'distribution'

urlpatterns = [
    path('mirrors/', views.MirrorListView.as_view(), name='mirror-list'),

    # Simple URL – assumes 'installer' artifact (most common case)
    path('file/<uuid:version_id>/', views.FileDownloadRedirectView.as_view(), name='file-simple'),

    # Explicit URL – specify artifact type (for advanced use)
    path('file/<uuid:version_id>/<str:artifact_type>/', views.FileDownloadRedirectView.as_view(), name='file-explicit'),
]