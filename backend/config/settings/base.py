"""
Django settings for software distribution platform.
Production-ready settings with configuration management.
"""
import os
from pathlib import Path
from datetime import timedelta
import environ
import logging

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
APPS_DIR = BASE_DIR / "backend" / "apps"

# Environment setup
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# Secret key
SECRET_KEY = env("SECRET_KEY", default="django-insecure-development-key-change-in-production")

# Debug mode
DEBUG = env.bool("DEBUG", default=False)

# Allowed hosts
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Application definition
INSTALLED_APPS = [
    # Custom apps (must be first for User model)
    "backend.apps.accounts",
    "backend.apps.products",
    "backend.apps.licenses",
    "backend.apps.payments",
    "backend.apps.distribution",
    "backend.apps.analytics",
    "backend.apps.notifications",
    "backend.apps.dashboard",
    "backend.apps.api",
    "backend.apps.security",
    
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Third party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    "storages",
    "django_celery_beat",
    "django_celery_results",
    "django_extensions",
    "debug_toolbar",
]

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "backend.core.middleware.SecurityHeadersMiddleware",
    "backend.core.middleware.PermissionAuditMiddleware",
]

# URL configuration
ROOT_URLCONF = "backend.config.urls"

# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "backend" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# WSGI/ASGI
WSGI_APPLICATION = "backend.config.wsgi.application"
ASGI_APPLICATION = "backend.config.asgi.application"

# Database - PostgreSQL is REQUIRED
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="software_platform"),
        "USER": env("POSTGRES_USER", default="postgres"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="postgres"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 600,
        "OPTIONS": {"sslmode": "prefer"},
    }
}

# Sessions
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"

# Cache - Redis with graceful degradation
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/1")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # REMOVED THIS LINE:"PARSER_CLASS": "redis.connection.HiredisParser",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100, "retry_on_timeout": True},
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": not DEBUG,
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
        },
        "KEY_PREFIX": "software_platform",
        "TIMEOUT": 60 * 15,
    }
}

# ============================================================================
# CELERY CONFIGURATION
# ============================================================================

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)

# Fallback to database if Redis not available - CORRECTED TYPO
if not CELERY_BROKER_URL.startswith("redis://"):
    CELERY_BROKER_URL = "django://"
    CELERY_RESULT_BACKEND = "django-db"  # ✅ FIXED: Changed from "django-database" to "django-db"

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=DEBUG)

# ============================================================================
# CELERY ENHANCED SETTINGS (Safe additions only)
# ============================================================================

# Celery enhanced settings (safe additions only)
CELERY_ENABLE_UTC = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = False
CELERY_TASK_STORE_ERRORS_EVEN_IF_IGNORED = True

# Task default queue (safe to add)
CELERY_TASK_DEFAULT_QUEUE = 'default'

# Worker settings with env vars (safe to add)
CELERY_WORKER_CONCURRENCY = env.int('CELERY_WORKER_CONCURRENCY', default=4)
CELERY_WORKER_PREFETCH_MULTIPLIER = env.int('CELERY_WORKER_PREFETCH_MULTIPLIER', default=1)
CELERY_WORKER_MAX_TASKS_PER_CHILD = env.int('CELERY_WORKER_MAX_TASKS_PER_CHILD', default=1000)

# ============================================================================

# Authentication
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "backend.core.exceptions.custom_exception_handler",
}

# JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# CORS
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[
    "http://localhost:3000",
    "http://127.0.0.1:3000",
])
CORS_ALLOW_CREDENTIALS = True

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 1209600

# ============================================================================
# EMAIL CONFIGURATION
# ============================================================================

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@softwareplatform.com")

# Additional email settings (safe to add)
EMAIL_TIMEOUT = 30
SUPPORT_EMAIL = env('SUPPORT_EMAIL', default='support@softwareplatform.com')
SERVER_EMAIL = env('SERVER_EMAIL', default='server@softwareplatform.com')

# ============================================================================
# FRONTEND URLS FOR EMAIL LINKS (Safe addition)
# ============================================================================

FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:3000')
ADMIN_FRONTEND_URL = env('ADMIN_FRONTEND_URL', default='http://localhost:3000/admin')

# ============================================================================

# Admin
ADMINS = [("System Admin", env("ADMIN_EMAIL", default="admin@example.com"))]

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "WARNING",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "django_redis": {
            "handlers": ["file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# File uploads
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB

# Activation keys (legacy)
ACTIVATION_KEY_LENGTH = 25
ACTIVATION_KEY_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ACTIVATION_EXPIRY_DAYS = 365

# ============================================================================
# LICENSE KEY AND ENCRYPTION SETTINGS (New consolidated settings)
# ============================================================================
LICENSE_KEY_SETTINGS = {
    'DEFAULT_KEY_FORMAT': 'STANDARD',
    'DEFAULT_KEY_LENGTH': 25,
    'DEFAULT_KEY_GROUPS': 4,
    'MAX_ACTIVATIONS_PER_KEY': 10,
    'DEFAULT_EXPIRY_DAYS': 365,
    'ALLOWED_KEY_FORMATS': ['STANDARD', 'EXTENDED', 'ALPHANUM'],
    'MIN_KEY_LENGTH': 20,
    'MAX_KEY_LENGTH': 30,
    'HARDWARE_ID_SALT': env('HARDWARE_ID_SALT', default=SECRET_KEY),
    'MAX_DEVICE_CHANGES': 3,
    'DEVICE_CHANGE_WINDOW_HOURS': 24,
    'LICENSE_ENCRYPTION_KEY_PATH': env('LICENSE_ENCRYPTION_KEY_PATH', default=None),
    'LICENSE_PRIVATE_KEY_PATH': env('LICENSE_PRIVATE_KEY_PATH', default=None),
    'LICENSE_PUBLIC_KEY_PATH': env('LICENSE_PUBLIC_KEY_PATH', default=None),
}

# AWS S3
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="")
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
AWS_DEFAULT_ACL = "private"
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 3600

# DRF Spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "Software Distribution Platform API",
    "DESCRIPTION": "Comprehensive API for software distribution",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/",
    "DEFAULT_GENERATOR_CLASS": "drf_spectacular.generators.SchemaGenerator",
}