# FILE: backend/apps/distribution/urls.py
from django.urls import path
from . import views

app_name = 'distribution'

urlpatterns = [
    path('mirrors/', views.MirrorListView.as_view(), name='mirror-list'),
    path('file/<uuid:version_id>/', views.FileDownloadRedirectView.as_view(), name='file-redirect'),
]