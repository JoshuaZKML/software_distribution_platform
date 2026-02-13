from django.apps import AppConfig

class HealthCheckConfig(AppConfig):
    """Configuration for the health_check app (views, templates, etc.)."""
    name = 'backend.apps.health_check'
    verbose_name = 'System Health'