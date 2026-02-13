from django.urls import path
from .views import super_admin_health_check, health_dashboard

urlpatterns = [
    # HTML dashboard – now at the root /health/
    path('', health_dashboard, name='health_check'),
    # JSON endpoint – moved to /health/json/
    path('json/', super_admin_health_check, name='health_check_json'),
]