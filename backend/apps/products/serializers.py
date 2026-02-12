# FILE: /backend/apps/products/serializers.py (CREATE NEW)
from rest_framework import serializers
from .models import Category, Software, SoftwareVersion, SoftwareImage, SoftwareDocument
from backend.apps.accounts.permissions import IsAdmin   # CORRECTED: import IsAdmin

class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for software categories.
    """
    software_count = serializers.IntegerField(read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description',
            'parent', 'parent_name', 'icon',
            'display_order', 'is_active',
            'software_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'software_count']


class SoftwareImageSerializer(serializers.ModelSerializer):
    """
    Serializer for software images.
    """
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    
    class Meta:
        model = SoftwareImage
        fields = [
            'id', 'software', 'image_type',
            'image_url', 'thumbnail_url',
            'alt_text', 'caption', 'display_order',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None
    
    def get_thumbnail_url(self, obj):
        # Placeholder – implement with django-imagekit if needed
        if obj.image:
            return obj.image.url
        return None


class SoftwareDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for software documents.
    """
    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    file_type = serializers.SerializerMethodField()
    
    class Meta:
        model = SoftwareDocument
        fields = [
            'id', 'software', 'document_type',
            'title', 'file_url', 'file_size', 'file_type',
            'description', 'language', 'version',
            'download_count', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'download_count']
    
    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None
    
    def get_file_size(self, obj):
        if obj.file:
            size = obj.file.size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        return "0 B"
    
    def get_file_type(self, obj):
        if obj.file:
            import os
            _, ext = os.path.splitext(obj.file.name)
            return ext.lower().replace('.', '')
        return None


class SoftwareVersionSerializer(serializers.ModelSerializer):
    """
    Serializer for software versions.
    """
    download_url = serializers.SerializerMethodField()
    file_size_human = serializers.SerializerMethodField()
    
    class Meta:
        model = SoftwareVersion
        fields = [
            'id', 'software', 'version_number', 'version_code',
            'release_name', 'release_notes', 'changelog',
            'binary_file', 'binary_size', 'file_size_human',
            'binary_checksum', 'installer_file',
            'download_url', 'download_count',
            'supported_os', 'min_requirements', 'recommended_requirements',
            'is_active', 'is_beta', 'is_stable', 'is_signed',
            'signature_file', 'created_at', 'updated_at', 'released_at'
        ]
        read_only_fields = [
            'id', 'binary_size', 'binary_checksum',
            'download_count', 'created_at', 'updated_at'
        ]
    
    def get_download_url(self, obj):
        request = self.context.get('request')
        if request and obj.software:
            return obj.software.get_download_url(version=obj)
        return None
    
    def get_file_size_human(self, obj):
        return obj.human_size
    
    def validate(self, attrs):
        software = attrs.get('software') or self.instance.software if self.instance else None
        version_number = attrs.get('version_number')
        
        if software and version_number:
            qs = SoftwareVersion.objects.filter(
                software=software,
                version_number=version_number
            )
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError({
                    'version_number': f'Version {version_number} already exists for this software.'
                })
        
        binary_file = attrs.get('binary_file')
        if binary_file:
            max_size = 2 * 1024 * 1024 * 1024
            if binary_file.size > max_size:
                raise serializers.ValidationError({
                    'binary_file': 'File size exceeds maximum allowed size of 2GB.'
                })
            allowed_extensions = ['.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm', '.zip', '.tar.gz']
            import os
            _, ext = os.path.splitext(binary_file.name)
            if ext.lower() not in allowed_extensions:
                raise serializers.ValidationError({
                    'binary_file': f'File type {ext} not allowed. Allowed types: {", ".join(allowed_extensions)}'
                })
        return attrs


class SoftwareSerializer(serializers.ModelSerializer):
    """
    Serializer for software products.
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    current_version = serializers.SerializerMethodField()
    versions = SoftwareVersionSerializer(many=True, read_only=True)
    images = SoftwareImageSerializer(many=True, read_only=True)
    documents = SoftwareDocumentSerializer(many=True, read_only=True)
    pricing_tiers = serializers.SerializerMethodField()
    supported_os = serializers.SerializerMethodField()
    
    class Meta:
        model = Software
        fields = [
            'id', 'name', 'slug', 'app_code',
            'category', 'category_name',
            'short_description', 'full_description',
            'features', 'requirements', 'tags',
            'base_price', 'currency', 'license_type',
            'pricing_tiers',
            'has_trial', 'trial_days', 'trial_features',
            'is_active', 'is_featured', 'is_new',
            'display_order', 'download_count',
            'average_rating', 'review_count',
            'supported_os',
            'current_version', 'versions', 'images', 'documents',
            'released_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'download_count', 'average_rating',
            'review_count', 'created_at', 'updated_at'
        ]
    
    def get_current_version(self, obj):
        version = obj.get_latest_version(include_beta=False)
        if version:
            return SoftwareVersionSerializer(version, context=self.context).data
        return None
    
    def get_pricing_tiers(self, obj):
        return obj.get_pricing_tiers()
    
    def get_supported_os(self, obj):
        return obj.get_supported_os_list()
    
    def validate(self, attrs):
        slug = attrs.get('slug')
        if slug:
            qs = Software.objects.filter(slug=slug)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError({
                    'slug': f'Software with slug "{slug}" already exists.'
                })
        
        app_code = attrs.get('app_code')
        if app_code:
            qs = Software.objects.filter(app_code=app_code)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError({
                    'app_code': f'Software with app code "{app_code}" already exists.'
                })
        
        base_price = attrs.get('base_price', 0)
        if base_price < 0:
            raise serializers.ValidationError({
                'base_price': 'Price cannot be negative.'
            })
        return attrs
    
    def create(self, validated_data):
        # Set default values
        validated_data.setdefault('download_count', 0)
        validated_data.setdefault('average_rating', 0.0)
        validated_data.setdefault('review_count', 0)
        
        software = Software.objects.create(**validated_data)
        
        if not software.category:
            default_category, _ = Category.objects.get_or_create(
                name='Uncategorized',
                slug='uncategorized',
                defaults={'description': 'Uncategorized software'}
            )
            software.category = default_category
            software.save()
        
        return software