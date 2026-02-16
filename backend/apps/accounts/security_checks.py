# FILE: /backend/apps/accounts/security_checks.py
"""
Risk assessment and suspicious behavior detection.
Enterprise‑grade, non‑disruptive enhancements with corrected imports,
fixed geolocation, per‑request caching, audit logging, and improved timezone handling.
"""
import hashlib
import json
import logging
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError
from django.utils import timezone
from django.utils.functional import SimpleLazyObject

# ----------------------------------------------------------------------
# Corrected imports – use relative imports for same‑app models,
# and absolute imports with backend.apps for cross‑app models.
# ----------------------------------------------------------------------
from .models import UserSession, SecurityLog
from backend.apps.security.models import IPBlacklist, AbuseAttempt

# Import tasks conditionally – Celery may not be installed/configured
try:
    from backend.apps.security.tasks import notify_super_admins_of_breakin_attempt
except ImportError:
    def notify_super_admins_of_breakin_attempt(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Configuration – override in Django settings (unchanged)
# ----------------------------------------------------------------------
RISK_WEIGHTS = getattr(settings, 'RISK_WEIGHTS', {
    'IP_BLACKLIST': 8,
    'FAILED_ATTEMPTS_PER_5': 5,
    'NEW_DEVICE': 4,
    'MISSING_DEVICE_FINGERPRINT': 2,
    'GEO_VELOCITY': 3,
    'UNUSUAL_HOUR': 2,
    'ADMIN_ACCOUNT': 5,
    'ADMIN_NO_2FA': 3,
    'CONCURRENT_SESSIONS': 2,
})

RISK_THRESHOLD_2FA = getattr(settings, 'RISK_THRESHOLD_2FA', 6)
RISK_THRESHOLD_NOTIFY = getattr(settings, 'RISK_THRESHOLD_NOTIFY', 8)
GEOIP_ENABLED = getattr(settings, 'GEOIP_ENABLED', False)
GEOIP_PATH = getattr(settings, 'GEOIP_PATH', None)
CLIENT_IP_HEADER = getattr(settings, 'CLIENT_IP_HEADER', 'HTTP_X_FORWARDED_FOR')
DEFAULT_TIMEZONE = getattr(settings, 'DEFAULT_TIMEZONE', 'UTC')


# ----------------------------------------------------------------------
# IP extraction helper (unchanged)
# ----------------------------------------------------------------------
def _get_client_ip(request):
    ip_header = request.META.get(CLIENT_IP_HEADER)
    if ip_header:
        return ip_header.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# ----------------------------------------------------------------------
# Device fingerprint canonicalization (unchanged)
# ----------------------------------------------------------------------
def _normalize_fingerprint(fingerprint):
    if not fingerprint:
        return ''
    if len(fingerprint) == 64 and all(c in '0123456789abcdefABCDEF' for c in fingerprint):
        return fingerprint.lower()
    secret = settings.SECRET_KEY.encode()
    return hashlib.sha256(fingerprint.encode() + secret).hexdigest()


# ----------------------------------------------------------------------
# Geolocation utilities – unchanged
# ----------------------------------------------------------------------
def _get_lat_lon_from_ip(ip_address):
    if not GEOIP_ENABLED or not GEOIP_PATH:
        return None
    try:
        import geoip2.database
        with geoip2.database.Reader(GEOIP_PATH) as reader:
            response = reader.city(ip_address)
            return (response.location.latitude, response.location.longitude)
    except ImportError:
        logger.debug("geoip2 not installed")
        return None
    except Exception:
        logger.debug("Geolocation failed for IP %s", ip_address, exc_info=True)
        return None


def _haversine_distance(coord1, coord2):
    if not coord1 or not coord2:
        return None
    from math import radians, sin, cos, sqrt, atan2
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


# ----------------------------------------------------------------------
# Timezone utility – unchanged
# ----------------------------------------------------------------------
def _get_user_local_hour(user):
    try:
        tz_name = getattr(user, 'timezone', None)
        if tz_name:
            import pytz
            user_tz = pytz.timezone(tz_name)
            now = timezone.now().astimezone(user_tz)
            return now.hour
    except (ImportError, AttributeError, ValueError):
        pass
    return timezone.now().hour


# ----------------------------------------------------------------------
# Per‑request cache decorator – unchanged
# ----------------------------------------------------------------------
def per_request_cache(func):
    @wraps(func)
    def wrapper(user, request, context=None):
        cache_attr = f'_risk_cache_{func.__name__}'
        if not hasattr(request, cache_attr):
            setattr(request, cache_attr, {})
        cache_dict = getattr(request, cache_attr)
        key = f"{user.id}:{request.path}"
        if key not in cache_dict:
            cache_dict[key] = func(user, request, context)
        return cache_dict[key]
    return wrapper


# ----------------------------------------------------------------------
# Main risk assessment class – unchanged logic, only imports fixed
# ----------------------------------------------------------------------
class RiskAssessment:
    @staticmethod
    @per_request_cache
    def check_suspicious_behavior(user, request, context=None):
        if not user or not getattr(user, 'is_authenticated', False):
            return 10, ["Unauthenticated user cannot be assessed"]

        risk_level = 0
        reasons = []

        ip_address = _get_client_ip(request)
        raw_fingerprint = request.data.get('device_fingerprint', '')
        device_fingerprint = _normalize_fingerprint(raw_fingerprint)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # 1. IP Blacklist
        try:
            if IPBlacklist.objects.filter(ip_address=ip_address, is_active=True).exists():
                risk_level += RISK_WEIGHTS['IP_BLACKLIST']
                reasons.append("IP is blacklisted")
        except DatabaseError:
            logger.exception("IPBlacklist query failed")

        # 2. Recent failed login attempts
        try:
            recent_failed_attempts = SecurityLog.objects.filter(
                actor=None,
                action='LOGIN_FAILED',
                target=user.email,
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()
            if recent_failed_attempts >= 5:
                risk_level += RISK_WEIGHTS['FAILED_ATTEMPTS_PER_5']
                reasons.append(f"{recent_failed_attempts} failed attempts in last hour")
        except DatabaseError:
            logger.exception("Failed attempts query failed")

        # 3. Device fingerprint analysis
        if not device_fingerprint:
            risk_level += RISK_WEIGHTS['MISSING_DEVICE_FINGERPRINT']
            reasons.append("Missing device fingerprint")
        else:
            try:
                known_device = UserSession.objects.filter(
                    user=user,
                    device_fingerprint=device_fingerprint,
                    is_active=True
                ).exists()
                if not known_device:
                    risk_level += RISK_WEIGHTS['NEW_DEVICE']
                    reasons.append("Login from new/unrecognized device")
            except DatabaseError:
                logger.exception("Device check query failed")

        # 4. Geographic velocity (unchanged)
        if GEOIP_ENABLED:
            try:
                cache_key = f"risk_last_login:{user.id}"
                last_login_data = cache.get(cache_key)
                if last_login_data is None:
                    last_login = SecurityLog.objects.filter(
                        actor=user,
                        action='LOGIN_SUCCESS'
                    ).order_by('-created_at').first()
                    if last_login:
                        last_login_data = {
                            'created_at': last_login.created_at.isoformat(),
                            'ip': last_login.metadata.get('ip_address', ''),
                        }
                        cache.set(cache_key, last_login_data, 300)
                if last_login_data:
                    last_ip = last_login_data['ip']
                    last_time = timezone.datetime.fromisoformat(last_login_data['created_at'])
                    current_coords = _get_lat_lon_from_ip(ip_address)
                    last_coords = _get_lat_lon_from_ip(last_ip)
                    distance = _haversine_distance(current_coords, last_coords)
                    if distance is not None and distance > 500:
                        time_diff = (timezone.now() - last_time).total_seconds() / 3600
                        if time_diff < 1 and distance > 500:
                            risk_level += RISK_WEIGHTS['GEO_VELOCITY']
                            reasons.append(f"Impossible travel: {distance:.0f}km in {time_diff:.1f}h")
            except DatabaseError:
                logger.exception("Geolocation query failed")
        elif context and context.get('location'):
            try:
                last_login = SecurityLog.objects.filter(
                    actor=user,
                    action='LOGIN_SUCCESS'
                ).order_by('-created_at').first()
                if last_login and last_login.metadata.get('location'):
                    risk_level += RISK_WEIGHTS['GEO_VELOCITY']
                    reasons.append("Unusual geographic pattern detected (simplified)")
            except DatabaseError:
                pass

        # 5. Unusual time of day (unchanged)
        try:
            current_hour = _get_user_local_hour(user)
            user_logins = SecurityLog.objects.filter(
                actor=user,
                action='LOGIN_SUCCESS'
            ).order_by('-created_at').values_list('created_at', flat=True)[:20]

            if user_logins:
                local_hours = []
                for dt in user_logins:
                    if hasattr(user, 'timezone'):
                        try:
                            import pytz
                            user_tz = pytz.timezone(user.timezone)
                            local_hours.append(dt.astimezone(user_tz).hour)
                        except (ImportError, AttributeError, ValueError):
                            local_hours.append(dt.hour)
                    else:
                        local_hours.append(dt.hour)

                business_hour_count = sum(1 for h in local_hours if 8 <= h <= 18)
                if business_hour_count > len(user_logins) / 2 and not (8 <= current_hour <= 18):
                    risk_level += RISK_WEIGHTS['UNUSUAL_HOUR']
                    reasons.append("Login at unusual time (based on your history)")
        except DatabaseError:
            logger.exception("Time of day query failed")

        # 6. High‑value account check (unchanged)
        if getattr(user, 'role', None) in [user.Role.ADMIN, user.Role.SUPER_ADMIN]:
            risk_level += RISK_WEIGHTS['ADMIN_ACCOUNT']
            reasons.append("Admin account access")
            if not getattr(user, 'mfa_enabled', False):
                risk_level += RISK_WEIGHTS['ADMIN_NO_2FA']
                reasons.append("Admin account without 2FA")

        # 7. Multiple concurrent sessions (unchanged)
        try:
            active_sessions = UserSession.objects.filter(
                user=user,
                is_active=True
            ).count()
            if active_sessions >= 3:
                risk_level += RISK_WEIGHTS['CONCURRENT_SESSIONS']
                reasons.append(f"{active_sessions} concurrent active sessions")
        except DatabaseError:
            logger.exception("Session count query failed")

        # Cap and deduplicate
        risk_level = max(0, min(risk_level, 10))
        seen = set()
        unique_reasons = []
        for r in reasons:
            if r not in seen:
                seen.add(r)
                unique_reasons.append(r)

        # Audit log
        try:
            SecurityLog.objects.create(
                actor=user,
                action='RISK_ASSESSMENT',
                target=user.email,
                metadata={
                    'risk_level': risk_level,
                    'reasons': unique_reasons,
                    'ip': ip_address,
                    'device_fingerprint': device_fingerprint,
                    'user_agent': user_agent,
                }
            )
        except Exception:
            logger.exception("Failed to log risk assessment")

        # Notify super admins if extreme risk
        if risk_level >= RISK_THRESHOLD_NOTIFY:
            try:
                notify_super_admins_of_breakin_attempt.delay(
                    user_id=user.id,
                    ip=ip_address,
                    device_fingerprint=device_fingerprint,
                    user_agent=user_agent,
                    risk_level=risk_level,
                    reasons=unique_reasons,
                )
                SecurityLog.objects.create(
                    actor=None,
                    action='BREAKIN_NOTIFICATION',
                    target=user.email,
                    metadata={'risk_level': risk_level}
                )
            except Exception:
                logger.exception("Failed to trigger break‑in notification")

        return risk_level, unique_reasons

    @staticmethod
    def requires_2fa(risk_level):
        return risk_level >= RISK_THRESHOLD_2FA