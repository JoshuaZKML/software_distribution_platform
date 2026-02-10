# backend/apps/products/views.py

from rest_framework import viewsets, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Category, Software, SoftwareVersion, SoftwareImage, SoftwareDocument

# Minimal serializers
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class SoftwareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Software
        fields = '__all__'

class SoftwareVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoftwareVersion
        fields = '__all__'

class SoftwareImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoftwareImage
        fields = '__all__'

class SoftwareDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoftwareDocument
        fields = '__all__'

# -------------------------------
# DRF ViewSets
# -------------------------------

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.none()
    serializer_class = CategorySerializer

class SoftwareViewSet(viewsets.ModelViewSet):
    queryset = Software.objects.none()
    serializer_class = SoftwareSerializer

class SoftwareVersionViewSet(viewsets.ModelViewSet):
    queryset = SoftwareVersion.objects.none()
    serializer_class = SoftwareVersionSerializer

class SoftwareImageViewSet(viewsets.ModelViewSet):
    queryset = SoftwareImage.objects.none()
    serializer_class = SoftwareImageSerializer

class SoftwareDocumentViewSet(viewsets.ModelViewSet):
    queryset = SoftwareDocument.objects.none()
    serializer_class = SoftwareDocumentSerializer

# -------------------------------
# APIViews
# -------------------------------

class FeaturedSoftwareView(APIView):
    def get(self, request):
        return Response({'status': 'FeaturedSoftwareView placeholder'})

class NewReleasesView(APIView):
    def get(self, request):
        return Response({'status': 'NewReleasesView placeholder'})

class SoftwareDownloadView(APIView):
    def get(self, request, slug):
        return Response({'status': f'SoftwareDownloadView placeholder for {slug}'})

class SoftwareVersionListView(APIView):
    def get(self, request, slug):
        return Response({'status': f'SoftwareVersionListView placeholder for {slug}'})
