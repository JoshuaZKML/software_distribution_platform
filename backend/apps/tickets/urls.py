from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import viewsets

router = DefaultRouter()
router.register(r'tickets', viewsets.TicketViewSet, basename='ticket')
router.register(r'ticket-bans', viewsets.TicketBanViewSet, basename='ticketban')

urlpatterns = [
    path('', include(router.urls)),
]