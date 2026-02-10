"""
Django settings for software distribution platform.
"""
import os
from pathlib import Path
from datetime import timedelta

# Try to use django-environ if available
try:
    import environ
except ImportError:
    environ = None

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
APPS_DIR = BASE_DIR / "backend" / "apps"

# Environment
if environ is not None:
    env = environ.Env()
    environ.Env.read_env(BASE_DIR / ".env")
else:
    class _DummyEnv:
        def __call__(self, key, default=None):
            return os.environ.get(key, default)

        def bool(self, key, default=False):
            val = os.environ.get(key)
            if val is None:
                return default
            return str(val).lower() in ("1", "true", "yes", "on")

        def int(self, key, default=0):
            val = os.environ.get(key)
            try:
                return int(val)
            except (TypeError, ValueError):
                return default

        def list(self, key, default=None):
            val = os.environ.get(key)
            if val is None:
                return default if default is not None else []
            return [v.strip() for v in val.split(",") if v.strip()]

    env = _DummyEnv()

# SECURITY WARNING: keep secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default="django-insecure-development-key-change-in-production")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ------------------------------------------------------
# Application definition
# ------------------------------------------------------

# CRITICAL FIX: Move LOCAL_APPS (with accounts.User) to the top
LOCAL_APPS = [
    "backend.apps.accounts",  # must be first for custom User model
    "backend.apps.products",
    "backend.apps.licenses",
    "backend.apps.payments",
    "backend.apps.distribution",
    "backend.apps.analytics",
    "backend.apps.notifications",
    "backend.apps.dashboard",
    "backend.apps.api",
    "backend.apps.security",
]

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    "storages",
    "django_celery_beat",
    "django_celery_results",
    "django_extensions",
    "debug_toolbar",
    "health_check",
    "health_check.db",
    "health_check.cache",
    "health_check.storage",
]

# Corrected INSTALLED_APPS order
INSTALLED_APPS = LOCAL_APPS + DJANGO_APPS + THIRD_PARTY_APPS

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

ROOT_URLCONF = "backend.config.urls"

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

WSGI_APPLICATION = "backend.config.wsgi.application"
ASGI_APPLICATION = "backend.config.asgi.application"

# ------------------------------------------------------
# Database
# ------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="software_platform"),
        "USER": env("POSTGRES_USER", default="django_user"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="StrongPassword123"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            "sslmode": "prefer",
        },
    }
}

# ------------------------------------------------------
# Cache & Sessions
# ------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100, "retry_on_timeout": True},
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
        },
        "KEY_PREFIX": "software_platform",
        "TIMEOUT": 60 * 15,
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# ------------------------------------------------------
# Password validation
# ------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------
# Internationalization
# ------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------
# Static & Media
# ------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ------------------------------------------------------
# Default primary key & Custom User
# ------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# ------------------------------------------------------
# REST Framework & JWT
# ------------------------------------------------------
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
    "EXCEPTION_HANDLER": "backend.core.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {"anon": "100/day", "user": "1000/day"},
}

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
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

# ------------------------------------------------------
# CORS & Security
# ------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000", "http://127.0.0.1:3000"])
CORS_ALLOW_CREDENTIALS = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# ------------------------------------------------------
# Email
# ------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@softwareplatform.com")

# ------------------------------------------------------
# Celery
# ------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# ------------------------------------------------------
# AWS S3 (optional)
# ------------------------------------------------------
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="")
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
AWS_DEFAULT_ACL = "private"
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 3600

# ------------------------------------------------------
# DRF Spectacular
# ------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Software Distribution Platform API",
    "DESCRIPTION": "Comprehensive API for software distribution with activation keys, licenses, and payments",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/",
    "DEFAULT_GENERATOR_CLASS": "drf_spectacular.generators.SchemaGenerator",
}

# ------------------------------------------------------
# Logging
# ------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}", "style": "{"},
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"level": "INFO", "class": "logging.StreamHandler", "formatter": "simple"},
        "file": {"level": "WARNING", "class": "logging.FileHandler", "filename": BASE_DIR / "logs" / "django.log", "formatter": "verbose"},
    },
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO", "propagate": True},
        "security": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
    },
}
