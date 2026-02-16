# FILE: /backend/config/__init__.py (UPDATE/REPLACE)
"""
Django configuration package for Software Distribution Platform.
This file ensures Celery is loaded when Django starts.
"""

from .celery import app as celery_app

# Make Celery app available as 'celery_app'
__all__ = ('celery_app',)

# Optional: Print startup message in development
import os
if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('.development'):
    print("[OK] Celery configured and ready")