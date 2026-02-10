# backend/apps/accounts/urls.py

from rest_framework import routers
from django.urls import path, include
from . import views

router = routers.DefaultRouter()

# Must give unique basenames because multiple ViewSets use the same User model
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'admin-profiles', views.AdminProfileViewSet, basename='admin-profile')
router.register(r'sessions', views.UserSessionViewSet, basename='session')
router.register(r'actions', views.AdminActionLogViewSet, basename='action')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', views.UserRegistrationView.as_view(), name='user-register'),
]
