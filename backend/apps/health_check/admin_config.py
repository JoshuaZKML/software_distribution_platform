from django.contrib.admin.apps import AdminConfig

class CustomAdminConfig(AdminConfig):
    """Replacement for django.contrib.admin – no `default = True` needed."""
    default_site = 'backend.apps.health_check.admin.HealthCheckAdminSite'