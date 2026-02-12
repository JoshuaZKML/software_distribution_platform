# FILE: /backend/apps/products/apps.py
from django.apps import AppConfig

class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backend.apps.products'
    
    def ready(self):
        import backend.apps.products.signals  # noqa