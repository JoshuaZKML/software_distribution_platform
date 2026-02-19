from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import viewsets

router = DefaultRouter()
router.register(r'sessions', viewsets.ChatSessionViewSet, basename='chatsession')
router.register(r'bans', viewsets.ChatBanViewSet, basename='chatban')

urlpatterns = [
    path('', include(router.urls)),
]