"""
Testing settings.
"""
from .base import *

DEBUG = False

# Use in-memory database for testing
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable password validation for testing
AUTH_PASSWORD_VALIDATORS = []

# Faster password hashing for testing
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Disable caching for testing
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# Disable email sending
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Disable CORS for testing
CORS_ALLOW_ALL_ORIGINS = True

# Test runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"
