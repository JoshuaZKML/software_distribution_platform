"""
Custom middleware for Software Distribution Platform.
"""
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseForbidden
import time
from django.core.cache import cache
from django.conf import settings
import hashlib

class SecurityHeadersMiddleware(MiddlewareMixin):
    """Add security headers to responses."""
    
    def process_response(self, request, response):
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Add CSP header in production
        if not settings.DEBUG:
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
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
    """Rate limiting middleware."""
    
    def process_request(self, request):
        # Skip rate limiting for certain paths
        exempt_paths = ['/health/', '/api/schema/', '/admin/']
        if any(request.path.startswith(path) for path in exempt_paths):
            return None
        
        # Get client IP
        ip = self.get_client_ip(request)
        
        # Create a key for rate limiting
        key = f'ratelimit:{ip}:{request.path}'
        
        # Get current count
        current = cache.get(key, 0)
        
        # Check if rate limit exceeded
        limit = getattr(settings, 'RATE_LIMIT_PER_MINUTE', 60)
        
        if current >= limit:
            return HttpResponseForbidden('Rate limit exceeded. Please try again later.')
        
        # Increment counter
        cache.set(key, current + 1, 60)  # Expire after 1 minute
        
        return None
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class DeviceFingerprintMiddleware(MiddlewareMixin):
    """Generate device fingerprint for requests."""
    
    def process_request(self, request):
        if not hasattr(request, 'device_fingerprint'):
            request.device_fingerprint = self.generate_fingerprint(request)
        return None
    
    def generate_fingerprint(self, request):
        """Generate device fingerprint from request data."""
        components = [
            request.META.get('HTTP_USER_AGENT', ''),
            request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            request.META.get('HTTP_ACCEPT_ENCODING', ''),
        ]
        
        # Add IP address if not in debug mode
        if not settings.DEBUG:
            ip = request.META.get('REMOTE_ADDR', '')
            components.append(ip)
        
        fingerprint_string = '|'.join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
