# FILE: /backend/apps/accounts/security_checks.py (NEW FILE)
"""
Risk assessment and suspicious behavior detection.
"""
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

class RiskAssessment:
    """Assess risk level for authentication attempts."""
    
    @staticmethod
    def check_suspicious_behavior(user, request, context=None):
        """
        Returns (risk_level, reasons) where:
        - risk_level: 0-10 (0=normal, 10=critical)
        - reasons: List of suspicious activities detected
        """
        risk_level = 0
        reasons = []
        
        from backend.apps.accounts.models import UserSession, SecurityLog
        from backend.apps.security.models import IPBlacklist, AbuseAttempt
        
        ip_address = request.META.get('REMOTE_ADDR', '')
        device_fingerprint = request.data.get('device_fingerprint', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # 1. Check IP Blacklist
        if IPBlacklist.objects.filter(
            ip_address=ip_address, 
            is_active=True
        ).exists():
            risk_level += 8
            reasons.append("IP is blacklisted")
        
        # 2. Recent failed login attempts (last 1 hour)
        recent_failed_attempts = SecurityLog.objects.filter(
            actor=None,
            action='LOGIN_FAILED',
            target=user.email,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_failed_attempts >= 5:
            risk_level += 5
            reasons.append(f"{recent_failed_attempts} failed login attempts in last hour")
        
        # 3. New device detection
        if device_fingerprint:
            known_device = UserSession.objects.filter(
                user=user,
                device_fingerprint=device_fingerprint,
                is_active=True
            ).exists()
            
            if not known_device:
                risk_level += 4
                reasons.append("Login from new/unrecognized device")
        
        # 4. Geographic velocity (if location data available)
        if context and context.get('location'):
            last_login = SecurityLog.objects.filter(
                actor=user,
                action='LOGIN_SUCCESS'
            ).order_by('-created_at').first()
            
            if last_login and last_login.metadata.get('location'):
                # Calculate distance/time between logins
                # This is simplified - you'd implement actual geolocation
                risk_level += 3
                reasons.append("Unusual geographic pattern detected")
        
        # 5. Unusual time of day (based on user's pattern)
        current_hour = timezone.now().hour
        if not (8 <= current_hour <= 18):  # Outside normal business hours
            user_logins = SecurityLog.objects.filter(
                actor=user,
                action='LOGIN_SUCCESS'
            ).values_list('created_at', flat=True)
            
            # Check if user normally logs in at this time
            normal_hours = any(8 <= login.hour <= 18 for login in user_logins[:10])
            if normal_hours:
                risk_level += 2
                reasons.append("Login at unusual time")
        
        # 6. High-value account check
        if user.role in [user.Role.ADMIN, user.Role.SUPER_ADMIN]:
            risk_level += 3
            reasons.append("Admin account access")
        
        # 7. Multiple concurrent sessions
        active_sessions = UserSession.objects.filter(
            user=user,
            is_active=True
        ).count()
        
        if active_sessions >= 3:
            risk_level += 2
            reasons.append(f"{active_sessions} concurrent active sessions")
        
        return min(risk_level, 10), reasons
    
    @staticmethod
    def requires_2fa(risk_level):
        """Determine if 2FA should be required based on risk level."""
        # Adjust threshold as needed
        return risk_level >= 6  # Medium-high risk requires 2FA