"""
Production settings for Django.
"""
from .base import *

# Production security
DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# HTTPS/SSL settings
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# CORS in production
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# Email in production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Database settings
DATABASES["default"]["CONN_MAX_AGE"] = 600
DATABASES["default"]["OPTIONS"]["sslmode"] = "require"

# Static files
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Cache settings for production
CACHES["default"]["OPTIONS"].update({
    "SOCKET_CONNECT_TIMEOUT": 5,
    "SOCKET_TIMEOUT": 5,
    "RETRY_ON_TIMEOUT": True,
    "IGNORE_EXCEPTIONS": True,
})

# Celery in production
CELERY_TASK_ALWAYS_EAGER = False

# Logging in production
LOGGING["loggers"]["django"]["level"] = "WARNING"
LOGGING["handlers"]["file"]["level"] = "ERROR"
