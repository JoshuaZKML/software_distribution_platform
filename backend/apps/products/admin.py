# FILE: /backend/apps/products/admin.py (CREATE)
from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Software, SoftwareVersion, SoftwareImage, SoftwareDocument

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'display_order', 'is_active', 'software_count')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('display_order', 'name')
    
    def software_count(self, obj):
        return obj.software.count()
    software_count.short_description = 'Software Count'


@admin.register(Software)
class SoftwareAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'app_code', 'category', 'base_price', 'currency', 
                    'is_active', 'is_featured', 'download_count', 'created_at')
    list_filter = ('is_active', 'is_featured', 'is_new', 'category', 'license_type')
    search_fields = ('name', 'slug', 'app_code', 'short_description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('download_count', 'average_rating', 'review_count', 'created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'app_code', 'category', 'tags')
        }),
        ('Description', {
            'fields': ('short_description', 'full_description', 'features', 'requirements')
        }),
        ('Pricing & Licensing', {
            'fields': ('base_price', 'currency', 'license_type', 'has_trial', 'trial_days', 'trial_features')
        }),
        ('Status & Display', {
            'fields': ('is_active', 'is_featured', 'is_new', 'display_order')
        }),
        ('Statistics', {
            'fields': ('download_count', 'average_rating', 'review_count', 'released_at')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['make_active', 'make_inactive', 'make_featured', 'remove_featured']
    
    def make_active(self, request, queryset):
        queryset.update(is_active=True)
    make_active.short_description = "Mark selected software as active"
    
    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)
    make_inactive.short_description = "Mark selected software as inactive"
    
    def make_featured(self, request, queryset):
        queryset.update(is_featured=True)
    make_featured.short_description = "Mark selected software as featured"
    
    def remove_featured(self, request, queryset):
        queryset.update(is_featured=False)
    remove_featured.short_description = "Remove featured status from selected software"


@admin.register(SoftwareVersion)
class SoftwareVersionAdmin(admin.ModelAdmin):
    list_display = ('software', 'version_number', 'version_code', 'is_active', 'is_beta', 
                    'is_stable', 'download_count', 'released_at')
    list_filter = ('is_active', 'is_beta', 'is_stable', 'is_signed', 'software')
    search_fields = ('version_number', 'version_code', 'release_name', 'release_notes')
    readonly_fields = ('binary_size', 'binary_checksum', 'download_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('software', 'version_number', 'version_code', 'release_name')
        }),
        ('Release Details', {
            'fields': ('release_notes', 'changelog', 'released_at')
        }),
        ('Files', {
            'fields': ('binary_file', 'binary_size', 'binary_checksum', 'installer_file', 'signature_file')
        }),
        ('Compatibility', {
            'fields': ('supported_os', 'min_requirements', 'recommended_requirements')
        }),
        ('Status', {
            'fields': ('is_active', 'is_beta', 'is_stable', 'is_signed')
        }),
        ('Statistics', {
            'fields': ('download_count',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['make_active', 'make_inactive', 'mark_as_stable', 'mark_as_beta']
    
    def make_active(self, request, queryset):
        queryset.update(is_active=True)
    make_active.short_description = "Mark selected versions as active"
    
    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)
    make_inactive.short_description = "Mark selected versions as inactive"
    
    def mark_as_stable(self, request, queryset):
        queryset.update(is_beta=False, is_stable=True)
    mark_as_stable.short_description = "Mark selected versions as stable"
    
    def mark_as_beta(self, request, queryset):
        queryset.update(is_beta=True, is_stable=False)
    mark_as_beta.short_description = "Mark selected versions as beta"


@admin.register(SoftwareImage)
class SoftwareImageAdmin(admin.ModelAdmin):
    list_display = ('software', 'image_type', 'display_order', 'is_active', 'image_preview')
    list_filter = ('image_type', 'is_active', 'software')
    readonly_fields = ('image_preview', 'created_at')
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" style="object-fit: cover;" />', obj.image.url)
        return "No image"
    image_preview.short_description = 'Preview'


@admin.register(SoftwareDocument)
class SoftwareDocumentAdmin(admin.ModelAdmin):
    list_display = ('software', 'document_type', 'title', 'language', 'version', 
                    'download_count', 'is_active')
    list_filter = ('document_type', 'language', 'is_active', 'software')
    search_fields = ('title', 'description')
    readonly_fields = ('download_count', 'created_at', 'updated_at')