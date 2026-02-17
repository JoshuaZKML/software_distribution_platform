# FILE: /backend/config/__init__.py (UPDATE/REPLACE)
"""
Django configuration package for Software Distribution Platform.
This file ensures Celery is loaded when Django starts (if available).
"""

try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery is optional - application works without it for development
    celery_app = None
    __all__ = ()

# Optional: Print startup message in development
import os
if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('.development'):
    if celery_app:
        print("[OK] Celery configured and ready")
    else:
        print("[INFO] Celery not available - using synchronous task execution")