"""
URL configuration for software distribution platform.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import HttpResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
import importlib


def _safe_include(module_path, url_prefix):
    """Safely include app URL modules; return None if import fails."""
    try:
        importlib.import_module(module_path)
        return path(url_prefix, include(module_path))
    except Exception:
        return None


def root_view(request):
    """Root view: redirect to API schema."""
    return HttpResponse(
        '<html><head><title>Software Distribution Platform</title></head>'
        '<body><h1>API Documentation</h1>'
        '<p><a href="/api/schema/swagger-ui/">Swagger UI</a> | '
        '<a href="/api/schema/redoc/">ReDoc</a></p></body></html>',
        content_type='text/html'
    )


def favicon_view(request):
    """Handle favicon.ico requests gracefully."""
    return HttpResponse(status=204)


urlpatterns = [
    path("", root_view, name="root"),
    path("favicon.ico", favicon_view, name="favicon"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Try to include app URL modules if they import cleanly; skip faulty apps so management
# commands (migrate/runserver) can start in development when some app URL modules
# still need implementation.
app_includes = [
    ("backend.apps.accounts.urls", "api/v1/auth/"),
    ("backend.apps.products.urls", "api/v1/products/"),
    ("backend.apps.licenses.urls", "api/v1/licenses/"),
    ("backend.apps.payments.urls", "api/v1/payments/"),
    ("backend.apps.dashboard.urls", "api/v1/dashboard/"),
    ("backend.apps.security.urls", "api/v1/security/"),
    ("backend.apps.api.urls", "api/v1/"),
    ("backend.apps.health_check.urls", "health/"),
]

for mod, prefix in app_includes:
    inc = _safe_include(mod, prefix)
    if inc is not None:
        urlpatterns.append(inc)

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Debug toolbar (only include if installed and importable)
    try:
        import debug_toolbar  # type: ignore
        urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
    except Exception:
        pass
