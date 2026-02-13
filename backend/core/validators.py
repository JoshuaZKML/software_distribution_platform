"""
Custom validators for Software Distribution Platform.
"""
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import ipaddress
from datetime import timedelta
from django.utils import timezone


def validate_activation_code_format(value):
    """Validate activation code format."""
    # Remove dashes for validation
    clean_value = value.replace('-', '')

    # Combined length + allowed characters check
    if not re.match(r'^[A-Z0-9]{20,30}$', clean_value):
        raise ValidationError(
            _('Activation code must be between 20 and 30 characters (excluding dashes) '
              'and contain only uppercase letters and numbers.'),
            code='invalid_format'
        )

    return value


def validate_device_fingerprint(value):
    """Validate device fingerprint format (SHA-256 hash)."""
    if len(value) != 64:
        raise ValidationError(
            _('Device fingerprint must be a 64-character SHA-256 hash.'),
            code='invalid_hash_length'
        )

    if not re.match(r'^[a-f0-9]+$', value):
        raise ValidationError(
            _('Device fingerprint must be a valid hexadecimal string.'),
            code='invalid_hash_format'
        )

    return value


def validate_ip_address(value):
    """Validate IP address format."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise ValidationError(
            _('Enter a valid IPv4 or IPv6 address.'),
            code='invalid_ip'
        )

    # Check for private/reserved IPs
    ip = ipaddress.ip_address(value)
    if ip.is_private or ip.is_reserved or ip.is_loopback:
        raise ValidationError(
            _('Private, reserved, or loopback IP addresses are not allowed.'),
            code='private_ip'
        )

    return value


def validate_license_expiry(value):
    """Validate license expiry date."""
    if value < timezone.now():
        raise ValidationError(
            _('License expiry date cannot be in the past.'),
            code='past_date'
        )

    max_expiry = timezone.now() + timedelta(days=365 * 10)  # 10 years max
    if value > max_expiry:
        raise ValidationError(
            _('License expiry date cannot be more than 10 years in the future.'),
            code='too_far_future'
        )

    return value


def validate_software_version(value):
    """Validate software version format."""
    # Standard version pattern: 1.2.3, 1.2.3.4, v1.2.3
    pattern = r'^(v)?(\d+)(\.\d+){0,3}$'
    if not re.match(pattern, value):
        raise ValidationError(
            _('Enter a valid version number (e.g., 1.2.3, v1.2.3.4).'),
            code='invalid_version'
        )

    return value


def validate_app_code(value):
    """Validate application code format."""
    # Format: ABC123, WINAPP001, etc.
    pattern = r'^[A-Z]{2,10}\d{1,5}$'
    if not re.match(pattern, value):
        raise ValidationError(
            _('Application code must start with 2-10 uppercase letters followed by 1-5 digits.'),
            code='invalid_app_code'
        )

    return value


def validate_price(value):
    """Validate price amount."""
    if value < 0:
        raise ValidationError(
            _('Price cannot be negative.'),
            code='negative_price'
        )

    if value > 1000000:  # 1 million max
        raise ValidationError(
            _('Price cannot exceed 1,000,000.'),
            code='price_too_high'
        )

    # Check decimal places using string conversion – works for Decimal, int, float
    str_val = str(value)
    if '.' in str_val:
        decimal_part = str_val.split('.')[1]
        if len(decimal_part) > 2:
            raise ValidationError(
                _('Price can have at most 2 decimal places.'),
                code='too_many_decimals'
            )

    return value


def validate_currency(value):
    """Validate currency code."""
    valid_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'CNY']
    if value not in valid_currencies:
        raise ValidationError(
            _(f'Currency must be one of: {", ".join(valid_currencies)}'),
            code='invalid_currency'
        )

    return value


class SecurityValidator:
    """Security-related validators."""

    @staticmethod
    def validate_rate_limit(user, action, limit_per_hour=60):
        """Validate rate limit for user actions (atomic counter)."""
        from django.core.cache import cache

        cache_key = f'rate_limit:{user.id}:{action}'

        # Initialize counter if not present, then atomically increment
        current_count = cache.get_or_set(cache_key, 0, 3600)
        if current_count >= limit_per_hour:
            raise ValidationError(
                _('Rate limit exceeded. Please try again later.'),
                code='rate_limit_exceeded'
            )

        cache.incr(cache_key)  # atomic, one round‑trip
        return True

    @staticmethod
    def validate_geolocation(ip_address, previous_ip, max_distance_km=800, max_time_hours=1):
        """
        Validate geographic velocity (impossible travel).

        Args:
            ip_address: Current IP address
            previous_ip: Previous IP address
            max_distance_km: Maximum allowed distance in km
            max_time_hours: Maximum time between attempts in hours
        """
        # This would integrate with a geolocation service
        # For now, return True (would be implemented with GeoIP database)
        return True

    @staticmethod
    def validate_device_change(user, new_fingerprint, max_changes_per_day=3):
        """Validate device change frequency."""
        # Get device changes in last 24 hours
        day_ago = timezone.now() - timedelta(days=1)
        changes_count = user.device_changes.filter(created_at__gte=day_ago).count()

        if changes_count >= max_changes_per_day:
            raise ValidationError(
                _('Too many device changes in 24 hours. Please contact support.'),
                code='too_many_device_changes'
            )

        return True