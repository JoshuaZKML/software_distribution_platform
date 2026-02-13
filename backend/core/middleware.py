"""
Custom middleware for Software Distribution Platform.
"""
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden
from django.core.cache import cache
from django.conf import settings
from django.utils.crypto import get_random_string
import hashlib
import time


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to responses with CSP nonce support."""

    def process_request(self, request):
        """Generate a cryptographically strong nonce for this request."""
        # Used to safely allow inline scripts in the CSP without 'unsafe-inline'
        request.csp_nonce = get_random_string(32)
        return None

    def process_response(self, request, response):
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Add strict CSP header in production – no unsafe-* for scripts, uses nonce
        if not settings.DEBUG:
            nonce = getattr(request, 'csp_nonce', '')
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )

        return response


class PermissionAuditMiddleware(MiddlewareMixin):
    """Audit permission checks for security monitoring."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Store view info for auditing
        request._audit_view = view_func.__name__
        request._audit_timestamp = time.time()
        return None

    def process_response(self, request, response):
        # Log permission checks if user is authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            audit_data = {
                'user': request.user.email,
                'view': getattr(request, '_audit_view', 'unknown'),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'timestamp': getattr(request, '_audit_timestamp', time.time()),
                'response_time': time.time() - getattr(request, '_audit_timestamp', time.time())
            }
            # Here you could log to database or external service
            # AuditLog.objects.create(**audit_data)

        return response


class RateLimitMiddleware(MiddlewareMixin):
    """Atomic rate limiting middleware using cache.incr()."""

    def process_request(self, request):
        # Skip rate limiting for certain paths
        exempt_paths = ['/health/', '/api/schema/', '/admin/']
        if any(request.path.startswith(path) for path in exempt_paths):
            return None

        ip = self.get_client_ip(request)
        key = f'ratelimit:{ip}:{request.path}'
        limit = getattr(settings, 'RATE_LIMIT_PER_MINUTE', 60)

        try:
            # Atomic increment – thread‑safe and one round‑trip
            current = cache.incr(key)
        except ValueError:
            # Key does not exist yet; set initial value 1 with 60s expiry
            cache.set(key, 1, 60)
            current = 1

        if current > limit:
            return HttpResponseForbidden('Rate limit exceeded. Please try again later.')

        return None

    def get_client_ip(self, request):
        """Get client IP address respecting X-Forwarded-For headers."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class DeviceFingerprintMiddleware(MiddlewareMixin):
    """Generate device fingerprint from request, using real client IP."""

    def process_request(self, request):
        if not hasattr(request, 'device_fingerprint'):
            request.device_fingerprint = self.generate_fingerprint(request)
        return None

    def get_client_ip(self, request):
        """Consistent IP extraction – matches RateLimitMiddleware."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def generate_fingerprint(self, request):
        """Generate device fingerprint from request data, using real client IP."""
        components = [
            request.META.get('HTTP_USER_AGENT', ''),
            request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            request.META.get('HTTP_ACCEPT_ENCODING', ''),
        ]

        # Use the real client IP when not in debug mode (prevents proxy collisions)
        if not settings.DEBUG:
            ip = self.get_client_ip(request)
            components.append(ip)

        fingerprint_string = '|'.join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()