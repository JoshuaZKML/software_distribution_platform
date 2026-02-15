# FILE: backend/apps/distribution/serializers.py
from rest_framework import serializers
from django.db.models import Prefetch
from .models import Mirror, CDNFile, MirrorFileStatus


class MirrorSerializer(serializers.ModelSerializer):
    """
    Basic mirror information for public or internal use.
    Excludes operational metrics (latency, failure count) for security.
    """
    class Meta:
        model = Mirror
        fields = ['id', 'name', 'base_url', 'region', 'priority', 'is_online']
        # If this serializer is ever used for writes, consider adding validation
        # for base_url scheme (https in production) – but that belongs at model level.
        read_only_fields = fields  # assume read‑only unless explicitly needed for admin


class CDNFileSerializer(serializers.ModelSerializer):
    """
    CDN file representation with a list of active mirrors where the file is synced.
    Performance critical: the view MUST prefetch `mirrorfilestatus_set` with
    `select_related('mirror')` and filter for active/online mirrors to avoid N+1 queries.
    """
    mirrors = serializers.SerializerMethodField()
    software_version_detail = serializers.StringRelatedField(
        source='software_version',
        read_only=True
    )

    class Meta:
        model = CDNFile
        fields = [
            'id', 'software_version', 'software_version_detail',
            'artifact_type', 'filename', 'file_hash', 'file_size', 'mirrors'
        ]
        read_only_fields = fields  # all read‑only for public API

    def get_mirrors(self, obj):
        """
        Return a list of mirrors where this file is synced, filtered for active/online mirrors,
        and sorted by priority (lower first).
        Assumes the view has prefetched:
            Prefetch(
                'mirrorfilestatus_set',
                queryset=MirrorFileStatus.objects.filter(
                    is_synced=True,
                    mirror__is_active=True,
                    mirror__is_online=True
                ).select_related('mirror').order_by('mirror__priority')
            )
        """
        statuses = getattr(obj, 'mirrorfilestatus_set', None)
        if statuses is None:
            # Fallback if prefetch not used – still works but slower (N+1)
            statuses = MirrorFileStatus.objects.filter(
                cdn_file=obj,
                is_synced=True,
                mirror__is_active=True,
                mirror__is_online=True
            ).select_related('mirror').order_by('mirror__priority')

        result = []
        for status in statuses:
            mirror = status.mirror
            result.append({
                'mirror_id': mirror.id,
                'mirror_name': mirror.name,
                'url': status.url,
                'region': mirror.region,
                'priority': mirror.priority,
            })
        return result


class MirrorFileStatusSerializer(serializers.ModelSerializer):
    """
    Detailed status of a file on a mirror, including sync state and error info.
    Intended for admin or internal monitoring, not for public API.
    """
    mirror_name = serializers.CharField(source='mirror.name', read_only=True)
    filename = serializers.CharField(source='cdn_file.filename', read_only=True)
    url = serializers.URLField(read_only=True)

    class Meta:
        model = MirrorFileStatus
        fields = [
            'id', 'mirror', 'mirror_name', 'cdn_file', 'filename',
            'url', 'is_synced', 'last_synced_at', 'error_message'
        ]
        read_only_fields = fields  # typically read‑only; if writes needed, create separate admin serializer