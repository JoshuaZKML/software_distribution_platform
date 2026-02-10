"""
Production settings.
"""
from .base import *

DEBUG = False

# Security settings for production
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# CORS settings for production
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# Email settings for production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Database for production
DATABASES["default"]["CONN_MAX_AGE"] = 600
DATABASES["default"]["OPTIONS"]["sslmode"] = "require"

# Static files for production
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Logging for production
LOGGING["handlers"]["file"]["level"] = "ERROR"
LOGGING["loggers"]["django"]["handlers"] = ["file"]
