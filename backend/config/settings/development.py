"""
Development settings for Django.
"""
from .base import *

# Enable debugging for development
DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ["*"]

# Disable security middleware for development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Enable CORS for frontend development
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://0.0.0.0:8000",
]

# Console email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# No connection pooling in development
DATABASES["default"]["CONN_MAX_AGE"] = 0

# Allow Redis failures in development
CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True

# Celery runs tasks synchronously in development
CELERY_TASK_ALWAYS_EAGER = True
