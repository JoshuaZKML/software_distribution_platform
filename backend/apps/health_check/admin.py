from django.contrib.admin import AdminSite
from django.urls import reverse


class HealthCheckAdminSite(AdminSite):
    site_header = "Software Distribution Platform Admin"
    site_title = "Admin Portal"
    index_title = "Dashboard"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['health_check_url'] = reverse('health_check')
        return super().index(request, extra_context)
