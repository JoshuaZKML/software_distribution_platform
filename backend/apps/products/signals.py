# FILE: /backend/apps/products/signals.py
"""
Signal handlers for product models.
Hardened for production: correct file change detection, atomic safety,
efficient updates, and accurate version deletion warnings.
All changes are backward‑compatible and non‑disruptive.
"""
import logging
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Software, SoftwareVersion

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Helper to detect if the binary file has changed
# ----------------------------------------------------------------------
def _binary_file_changed(instance):
    """Return True if the binary_file field differs from the saved state."""
    if not instance.pk:
        return bool(instance.binary_file)  # new instance with file
    try:
        old = SoftwareVersion.objects.get(pk=instance.pk)
        return old.binary_file != instance.binary_file
    except SoftwareVersion.DoesNotExist:
        return bool(instance.binary_file)


# ----------------------------------------------------------------------
# Pre‑save: update checksum and file size ONLY when the file changes
# ----------------------------------------------------------------------
@receiver(pre_save, sender=SoftwareVersion)
def update_binary_metadata(sender, instance, **kwargs):
    """
    Update binary size and SHA‑256 checksum when the binary file changes.
    This replaces two separate signals with a single, efficient handler.
    - Only runs when the file actually changes (not on every save).
    - Does NOT block on large files (still synchronous; see comment below).
    """
    if _binary_file_changed(instance):
        # Update file size from the uploaded file
        if instance.binary_file:
            instance.binary_size = instance.binary_file.size
            # Recalculate checksum only if it's missing or file changed
            # (Calculate even if checksum already exists, because new file)
            instance.binary_checksum = instance.calculate_checksum()
        else:
            # File was removed – clear size and checksum
            instance.binary_size = 0
            instance.binary_checksum = ''


# ----------------------------------------------------------------------
# Post‑save: update parent software metadata, but only after commit
# ----------------------------------------------------------------------
@receiver(post_save, sender=SoftwareVersion)
def update_software_metadata(sender, instance, created, **kwargs):
    """
    Update parent software's `updated_at` timestamp when a new version is added.
    Runs inside a transaction.on_commit hook to ensure it only happens if the
    version save is successfully committed. This avoids unnecessary writes if
    the transaction is rolled back.
    """
    if created:
        def _do_update():
            Software.objects.filter(pk=instance.software_id).update(
                updated_at=timezone.now()
            )
        transaction.on_commit(_do_update)


# ----------------------------------------------------------------------
# Post‑delete: warn if this deletion leaves no active versions
# ----------------------------------------------------------------------
@receiver(post_delete, sender=SoftwareVersion)
def warn_last_active_version_deleted(sender, instance, **kwargs):
    """
    Log a warning when the last active version of a software product is deleted.
    Runs after deletion so the count reflects the current state.
    """
    active_versions = instance.software.versions.filter(is_active=True).count()
    if active_versions == 0:
        logger.warning(
            "Last active version of %s (ID: %s) deleted",
            instance.software.name,
            instance.software_id
        )