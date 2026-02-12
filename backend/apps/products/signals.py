# FILE: /backend/apps/products/signals.py
from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Software, SoftwareVersion

@receiver(pre_save, sender=SoftwareVersion)
def calculate_checksum_on_save(sender, instance, **kwargs):
    """
    Calculate checksum for binary file on save.
    """
    if instance.binary_file and not instance.binary_checksum:
        instance.binary_checksum = instance.calculate_checksum()

@receiver(pre_save, sender=SoftwareVersion)
def update_file_size(sender, instance, **kwargs):
    """
    Update file size when binary file changes.
    """
    if instance.binary_file:
        instance.binary_size = instance.binary_file.size

@receiver(post_save, sender=SoftwareVersion)
def update_software_metadata(sender, instance, created, **kwargs):
    """
    Update software metadata when new version is added.
    """
    if created:
        software = instance.software
        software.updated_at = timezone.now()
        software.save()

@receiver(pre_delete, sender=SoftwareVersion)
def handle_version_deletion(sender, instance, **kwargs):
    """
    Handle cleanup when software version is deleted.
    """
    active_versions = instance.software.versions.filter(is_active=True).count()
    if active_versions <= 1:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Deleting last active version of {instance.software.name}")