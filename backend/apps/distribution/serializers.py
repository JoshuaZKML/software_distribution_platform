# FILE: backend/apps/distribution/serializers.py
from rest_framework import serializers
from .models import Mirror, CDNFile, MirrorFileStatus


class MirrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mirror
        fields = ['id', 'name', 'base_url', 'region', 'priority', 'is_online']


class CDNFileSerializer(serializers.ModelSerializer):
    mirrors = serializers.SerializerMethodField()

    class Meta:
        model = CDNFile
        fields = ['id', 'software_version', 'artifact_type', 'filename',
                  'file_hash', 'file_size', 'mirrors']

    def get_mirrors(self, obj):
        # Return list of mirrors where file is synced, with their URL
        statuses = MirrorFileStatus.objects.filter(
            cdn_file=obj,
            is_synced=True
        ).select_related('mirror')
        return [
            {
                'mirror_id': status.mirror.id,
                'mirror_name': status.mirror.name,
                'url': status.url,
                'region': status.mirror.region,
                'priority': status.mirror.priority,
            }
            for status in statuses
        ]


class MirrorFileStatusSerializer(serializers.ModelSerializer):
    mirror_name = serializers.CharField(source='mirror.name', read_only=True)
    filename = serializers.CharField(source='cdn_file.filename', read_only=True)
    url = serializers.URLField(read_only=True)

    class Meta:
        model = MirrorFileStatus
        fields = ['id', 'mirror', 'mirror_name', 'cdn_file', 'filename',
                  'url', 'is_synced', 'last_synced_at', 'error_message']