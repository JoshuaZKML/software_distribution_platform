"""
Custom middleware for Software Distribution Platform.
"""
import base64
import binascii
import hashlib
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden
from django.utils.crypto import get_random_string
from django.utils.deprecation import MiddlewareMixin


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
    """Atomic rate limiting middleware using cache.incr() with robust error handling."""

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
        except Exception as e:
            # FIX: Handle any other cache backend errors gracefully
            # Log the error but allow the request to proceed
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Rate limiting error: {e}")
            return None

        # FIX: Ensure current is an integer before comparison
        if current is None:
            # If for some reason we got None, treat as 1 (first request)
            current = 1

        try:
            if int(current) > limit:
                return HttpResponseForbidden('Rate limit exceeded. Please try again later.')
        except (TypeError, ValueError):
            # If conversion to int fails, allow the request
            pass

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


class BasicAuthDocsMiddleware(MiddlewareMixin):
    """
    Protect only the API documentation URLs with Basic Authentication.
    Credentials are taken from settings.BASIC_AUTH_USERNAME/PASSWORD.
    """

    def process_request(self, request):
        # Check if the requested path matches any of the protected URLs
        protected_paths = getattr(settings, 'BASIC_AUTH_URLS', [])
        if not any(request.path.startswith(path) for path in protected_paths):
            return None  # not protected

        # Get credentials from Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Basic '):
            return self._unauthorized()

        try:
            auth_decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
            username, password = auth_decoded.split(':', 1)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return self._unauthorized()

        expected_username = getattr(settings, 'BASIC_AUTH_USERNAME', 'docs')
        expected_password = getattr(settings, 'BASIC_AUTH_PASSWORD', 'your-strong-password')

        if username == expected_username and password == expected_password:
            return None  # authenticated
        return self._unauthorized()

    def _unauthorized(self):
        response = HttpResponse('Unauthorized', content_type='text/plain', status=401)
        response['WWW-Authenticate'] = 'Basic realm="Documentation"'
        return response