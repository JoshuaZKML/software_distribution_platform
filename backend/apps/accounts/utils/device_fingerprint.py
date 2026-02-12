# FILE: /backend/apps/accounts/utils/device_fingerprint.py
import hashlib
from django.conf import settings

class DeviceFingerprintGenerator:
    """
    Enhanced device fingerprint generator.
    Extends existing User.generate_device_fingerprint().
    """
    
    @staticmethod
    def generate(request, user_agent=None, extra_data=None):
        """
        Generate device fingerprint from request data.
        Compatible with User.generate_device_fingerprint().
        """
        from ..models import User
        
        # Use existing method as base (ensures consistency)
        if hasattr(User, 'generate_device_fingerprint'):
            # Create dummy request wrapper for compatibility
            class DummyRequest:
                def __init__(self, request, user_agent):
                    self.META = request.META.copy()
                    if user_agent:
                        self.META['HTTP_USER_AGENT'] = user_agent
            dummy = DummyRequest(request, user_agent)
            fingerprint = User.generate_device_fingerprint(None, dummy)
        else:
            # Fallback (should never happen)
            fingerprint = DeviceFingerprintGenerator._legacy_generate(request, user_agent)
        
        # Add extra data if provided
        if extra_data:
            components = [fingerprint]
            for key, value in extra_data.items():
                components.append(f"{key}:{value}")
            components.sort()
            fingerprint = hashlib.sha256("|".join(components).encode()).hexdigest()
        
        return fingerprint
    
    @staticmethod
    def _legacy_generate(request, user_agent=None):
        """Fallback generator (same logic as User.generate_device_fingerprint)."""
        components = [
            user_agent or request.META.get('HTTP_USER_AGENT', ''),
            request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            request.META.get('REMOTE_ADDR', ''),
        ]
        fingerprint_string = "|".join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    @staticmethod
    def parse_platform(user_agent):
        """Parse platform from user agent string."""
        ua = user_agent.lower() if user_agent else ''
        if 'windows' in ua:
            return 'windows'
        elif 'mac' in ua:
            return 'macos'
        elif 'linux' in ua:
            return 'linux'
        elif 'android' in ua:
            return 'android'
        elif 'iphone' in ua or 'ipad' in ua:
            return 'ios'
        else:
            return 'unknown'
    
    @staticmethod
    def is_suspicious_change(user, request, new_fingerprint):
        """
        Detect suspicious device change patterns.
        Reuses your existing DeviceChangeLog model.
        """
        from datetime import timedelta
        from django.utils import timezone
        from ..models import DeviceChangeLog
        
        # Check recent device changes (last hour)
        hour_ago = timezone.now() - timedelta(hours=1)
        recent_changes = DeviceChangeLog.objects.filter(
            user=user,
            created_at__gte=hour_ago
        ).count()
        
        if recent_changes >= 3:
            return True, "Multiple device changes in short time"
        
        # Check IP reputation (simplified)
        ip_address = request.META.get('REMOTE_ADDR')
        # In production, integrate with your AbuseAttempt/IPBlacklist models
        from ...security.models import IPBlacklist
        if IPBlacklist.objects.filter(ip_address=ip_address, is_active=True).exists():
            return True, "IP address is blacklisted"
        
        return False, ""