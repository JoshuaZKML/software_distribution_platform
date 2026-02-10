"""
Development settings.
"""
from .base import *

# Debug Toolbar settings - ADDED as per instruction
INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
]

# Disable throttling in development - ADDED as per instruction
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["anon"] = None
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["user"] = None

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Security settings for development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# CORS settings for development
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Logging for development
LOGGING["loggers"]["django"]["level"] = "DEBUG"
LOGGING["handlers"]["console"]["level"] = "DEBUG"

# Database for development (can be overridden with .env)
DATABASES["default"]["CONN_MAX_AGE"] = 0  # Disable persistent connections

# Development uses PostgreSQL 17 as configured in .env
# No SQLite fallback - PostgreSQL is required for this project
