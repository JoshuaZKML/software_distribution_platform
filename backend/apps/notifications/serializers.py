# backend/apps/notifications/serializers.py
from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification model.
    All fields are read‑only by default to prevent client modification.
    Includes user and context metadata for richer client integration.
    """
    class Meta:
        model = Notification
        fields = [
            'id',
            'user',                # added: who the notification belongs to
            'channel',
            'subject',
            'body',
            'html_body',
            'context',             # added: JSON metadata (e.g., target URL)
            'status',
            'sent_at',
            'opened_at',
            'clicked_at',
            'created_at',
        ]
        # All fields are read‑only – suitable for the current GET‑only endpoints.
        read_only_fields = fields

        # ----- FUTURE ENHANCEMENT NOTES -----
        # If you later add an endpoint to mark notifications as read,
        # remove 'status' from read_only_fields and add an update method:
        #
        # read_only_fields = ['id', 'user', 'channel', 'subject', 'body',
        #                     'html_body', 'context', 'sent_at', 'opened_at',
        #                     'clicked_at', 'created_at']
        #
        # def update(self, instance, validated_data):
        #     # Only allow updating the status field
        #     instance.status = validated_data.get('status', instance.status)
        #     instance.save()
        #     return instance
        #
        # For list views with many notifications, consider creating a
        # separate lightweight serializer that omits body/html_body to
        # reduce payload size.