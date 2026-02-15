from rest_framework import serializers
from django.conf import settings
from .models import DailyAggregate, ExportJob, CohortAggregate

# 👇 ADD THESE TWO IMPORTS (drf-spectacular type hints)
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes


class DailyAggregateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyAggregate
        fields = '__all__'
        # Make all fields read‑only by collecting actual field names
        read_only_fields = tuple(field.name for field in model._meta.fields)

    # Optional: if you prefer to explicitly list fields for security, replace fields = '__all__' with:
    # fields = [
    #     'id', 'date', 'total_users', 'active_users', 'new_users',
    #     'total_sales', 'total_orders', 'licenses_activated',
    #     'licenses_expired', 'total_usage_events', 'abuse_attempts',
    #     'created_at', 'updated_at'
    # ]


class ExportJobSerializer(serializers.ModelSerializer):
    """
    Serializer for ExportJob – provides a secure file URL (signed S3 URL if using private storage,
    otherwise a link to the authenticated download endpoint).
    """
    file_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ExportJob
        fields = [
            'id', 'export_type', 'status', 'parameters', 'file',
            'file_url', 'error_message', 'created_by', 'created_at',
            'updated_at', 'completed_at'
        ]
        read_only_fields = ['id', 'status', 'file', 'error_message',
                            'created_by', 'created_at', 'updated_at', 'completed_at']

    # 👇 ADDED @extend_schema_field DECORATOR
    @extend_schema_field(OpenApiTypes.URI)
    def get_file_url(self, obj):
        """Return a secure URL to download the file."""
        if obj.status != 'completed' or not obj.file:
            return None
        # If using private S3 storage, this will generate a signed URL automatically
        # if AWS_QUERYSTRING_AUTH = True is set.
        try:
            return obj.file.url
        except Exception:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(f"/api/v1/analytics/exports/{obj.pk}/download/")
        return None


class CohortAggregateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CohortAggregate
        fields = '__all__'
        # Explicit read‑only fields (safer than referencing __all__)
        read_only_fields = [field.name for field in CohortAggregate._meta.fields]