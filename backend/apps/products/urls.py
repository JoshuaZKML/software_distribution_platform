"""
Products app URLs for Software Distribution Platform.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'software', views.SoftwareViewSet, basename='software')
router.register(r'versions', views.SoftwareVersionViewSet, basename='softwareversion')
router.register(r'images', views.SoftwareImageViewSet, basename='softwareimage')
router.register(r'documents', views.SoftwareDocumentViewSet, basename='softwaredocument')

urlpatterns = [
    path('', include(router.urls)),
    path('featured/', views.FeaturedSoftwareView.as_view(), name='featured-software'),
    path('new-releases/', views.NewReleasesView.as_view(), name='new-releases'),
    path('<slug:slug>/download/', views.SoftwareDownloadView.as_view(), name='software-download'),
    path('<slug:slug>/versions/', views.SoftwareVersionListView.as_view(), name='software-versions'),
    # Added: download specific version with token
    path('<slug:slug>/download/<uuid:version_id>/', views.SoftwareDownloadView.as_view(), name='software-version-download'),
]