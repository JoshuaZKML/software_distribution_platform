"""
Settings package for software distribution platform.
Uses modular approach with base/dev/prod/testing settings.
"""
from .base import *

# Determine which settings to use based on environment
import os

DJANGO_ENV = os.environ.get('DJANGO_ENV', 'development')

if DJANGO_ENV == 'production':
    from .production import *
elif DJANGO_ENV == 'testing':
    from .testing import *
else:
    from .development import *