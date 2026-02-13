"""
Production settings for Django.

This file extends base settings with production‑hardened configurations.
All changes are backward‑compatible and aim to strengthen security and reliability.
"""
from .base import *

# Production security
DEBUG = False

# ALLOWED_HOSTS must be explicitly set in environment.
# Removing default prevents silent misconfiguration that would cause DisallowedHost errors.
# If the environment variable is missing, the app will fail fast at startup (safer).
ALLOWED_HOSTS = env.list("ALLED_HOSTS")  # No default – must be set in production

# HTTPS/SSL settings
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Additional security headers (hardening)
SECURE_CONTENT_TYPE_NOSNIFF = True      # Prevents MIME type sniffing
SECURE_BROWSER_XSS_FILTER = True        # Enables browser XSS filtering
X_FRAME_OPTIONS = "DENY"                 # Prevents clickjacking
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"  # Controls referrer info

# CORS in production
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
# Allow credentials (cookies, authorization headers) if using session or JWT in cookies
CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins – required when frontend is on a different domain
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

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
    # IGNORE_EXCEPTIONS hides cache failures; for high‑reliability systems consider
    # logging failures instead of ignoring them.
    "IGNORE_EXCEPTIONS": True,
})

# Celery in production
CELERY_TASK_ALWAYS_EAGER = False

# Logging in production – currently minimal. For observability, consider structured
# JSON logging and separate loggers for security, Celery, and requests.
LOGGING["loggers"]["django"]["level"] = "WARNING"
LOGGING["handlers"]["file"]["level"] = "ERROR"

# SECRET_KEY must be set in environment – overriding any default from base.
# This ensures a strong, unique key is used in production.
SECRET_KEY = env("SECRET_KEY")