# backend/apps/accounts/views.py

from rest_framework import viewsets, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import User  # Ensure your custom user model exists

# Minimal serializer for placeholder purposes
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'

# -------------------------------
# ViewSets for DRF routers
# -------------------------------

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class AdminProfileViewSet(viewsets.ModelViewSet):
    queryset = User.objects.none()  # placeholder
    serializer_class = UserSerializer

class UserSessionViewSet(viewsets.ModelViewSet):
    queryset = User.objects.none()  # placeholder
    serializer_class = UserSerializer

class AdminActionLogViewSet(viewsets.ModelViewSet):
    queryset = User.objects.none()  # placeholder
    serializer_class = UserSerializer

# -------------------------------
# APIViews
# -------------------------------

class UserRegistrationView(APIView):
    def get(self, request):
        return Response({'status': 'UserRegistrationView placeholder'})
