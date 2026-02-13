# FILE: /backend/apps/accounts/serializers.py (FULLY UPDATED – with non‑disruptive refactoring)
from typing import Optional
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from .models import User, AdminProfile, UserSession, DeviceChangeLog


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    role = serializers.ChoiceField(
        choices=User.Role.choices,
        default=User.Role.USER
    )

    class Meta:
        model = User
        fields = [
            'email', 'password', 'password2', 'role',
            'first_name', 'last_name', 'company', 'phone'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })

        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({
                "email": "A user with this email already exists."
            })

        request = self.context.get('request')
        if request and request.user.is_authenticated:
            current_user_role = request.user.role
            requested_role = attrs.get('role', User.Role.USER)
            if requested_role in [User.Role.ADMIN, User.Role.SUPER_ADMIN]:
                if current_user_role != User.Role.SUPER_ADMIN:
                    raise serializers.ValidationError({
                        "role": "Only Super Admins can create admin users."
                    })

        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data.get('role', User.Role.USER),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            company=validated_data.get('company', ''),
            phone=validated_data.get('phone', ''),
            is_verified=False
        )

        if user.role in [User.Role.ADMIN, User.Role.SUPER_ADMIN]:
            AdminProfile.objects.create(user=user)

        from .tasks import send_verification_email
        send_verification_email.delay(user.id)

        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    device_fingerprint = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Device fingerprint for security validation"
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        device_fingerprint = attrs.get('device_fingerprint', '')
        request = self.context.get('request')

        user = authenticate(request=request, username=email, password=password)
        if not user:
            raise serializers.ValidationError({'email': 'Invalid email or password.'})
        if not user.is_verified:
            raise serializers.ValidationError({'email': 'Please verify your email before logging in.'})
        if user.is_blocked:
            raise serializers.ValidationError({'email': 'Your account has been blocked. Please contact support.'})

        # Device fingerprint validation for admins – extracted for clarity
        self._validate_admin_device(user, device_fingerprint, request)

        # Update user login metadata
        user.last_login = timezone.now()
        user.last_login_ip = request.META.get('REMOTE_ADDR', '')
        if device_fingerprint and not user.hardware_fingerprint:
            user.hardware_fingerprint = device_fingerprint
            user.last_device_change = timezone.now()
        user.save()

        from .models import UserSession
        UserSession.objects.create(
            user=user,
            session_key=request.session.session_key if request.session else '',
            device_fingerprint=device_fingerprint or user.hardware_fingerprint,
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            location=self._get_location_from_ip(request.META.get('REMOTE_ADDR', ''))
        )

        refresh = self.get_token(user)
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': str(user.id),
                'email': user.email,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_verified': user.is_verified,
                'requires_2fa': user.mfa_enabled
            }
        }
        if user.mfa_enabled:
            data['requires_2fa'] = True
            data['mfa_token'] = self._generate_mfa_token(user)
        return data

    # ------------------------------------------------------------------
    # Helper methods (non‑disruptive extraction)
    # ------------------------------------------------------------------

    def _validate_admin_device(self, user: User, device_fingerprint: str, request) -> None:
        """
        Perform device‑based security checks for admin users.
        Logs device changes and triggers verification if necessary.
        """
        if user.role not in [User.Role.ADMIN, User.Role.SUPER_ADMIN]:
            return
        if not device_fingerprint:
            return

        if user.hardware_fingerprint and user.hardware_fingerprint != device_fingerprint:
            from .models import DeviceChangeLog
            DeviceChangeLog.objects.create(
                user=user,
                old_fingerprint=user.hardware_fingerprint,
                new_fingerprint=device_fingerprint,
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            if not self.context.get('skip_device_check', False):
                self._send_device_verification_email(user, device_fingerprint, request)
                raise serializers.ValidationError({
                    'device_change': True,
                    'message': 'New device detected. Verification email sent.'
                })

    def _send_device_verification_email(self, user: User, new_fingerprint: str, request) -> None:
        """
        Create a device verification record and dispatch an email asynchronously.
        """
        from .utils.device_verification import DeviceVerificationManager
        from .tasks import send_device_verification_email

        device_log, verification_code = DeviceVerificationManager.create_verification(
            user, new_fingerprint, request
        )
        send_device_verification_email.delay(
            user_id=user.id,
            device_log_id=device_log.id,
            verification_token=device_log.verification_token,
            verification_code=verification_code
        )

    def _generate_mfa_token(self, user: User) -> str:
        """
        Generate a current TOTP token for a user with MFA enabled.
        """
        import pyotp
        totp = pyotp.TOTP(user.mfa_secret)
        return totp.now()

    def _get_location_from_ip(self, ip_address: str) -> str:
        """
        Attempt to geolocate an IP address.
        If geoip2 is not installed, gracefully fall back to a placeholder.
        """
        try:
            import geoip2.database  # noqa: F401
            # To actually use GeoIP, you need to:
            #   - install geoip2 (pip install geoip2)
            #   - download a GeoLite2 database and set GEOIP_PATH in settings
            #   - uncomment the lines below and remove the placeholder return.
            # from django.conf import settings
            # with geoip2.database.Reader(settings.GEOIP_PATH) as reader:
            #     response = reader.city(ip_address)
            #     return f"{response.city.name}, {response.country.name}"
            return "Unknown Location"
        except ImportError:
            return "Location service not available"
        except Exception:
            return "Unknown"


# ----------------------------
# Password Reset Serializers
# ----------------------------

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            if not user.is_active:
                raise serializers.ValidationError("User account is inactive.")
            if user.is_blocked:
                raise serializers.ValidationError("User account is blocked.")
            return value
        except User.DoesNotExist:
            # Do not reveal that user does not exist
            return value

    def create_reset_token(self, user):
        import hashlib, secrets, base64
        from django.utils import timezone

        timestamp = str(int(timezone.now().timestamp()))
        random_string = secrets.token_urlsafe(32)
        token_string = f"{user.id}|{user.email}|{timestamp}|{random_string}"
        signature = hashlib.sha256(f"{token_string}{settings.SECRET_KEY}".encode()).hexdigest()[:32]
        full_token = f"{token_string}|{signature}"
        return base64.urlsafe_b64encode(full_token.encode()).decode()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        user = self._validate_token(attrs['token'])
        if not user:
            raise serializers.ValidationError({'token': 'Invalid or expired reset token.'})
        attrs['user'] = user
        return attrs

    def _validate_token(self, token):
        try:
            import base64, hashlib
            from datetime import datetime, timedelta
            from django.utils import timezone

            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            parts = decoded.split('|')
            if len(parts) != 5:
                return None

            user_id, email, timestamp, random_string, signature = parts
            expected_signature = hashlib.sha256(f"{user_id}|{email}|{timestamp}|{random_string}{settings.SECRET_KEY}".encode()).hexdigest()[:32]
            if signature != expected_signature:
                return None

            token_time = datetime.fromtimestamp(int(timestamp))
            if timezone.now() - token_time > timedelta(hours=1):
                return None

            try:
                user = User.objects.get(id=user_id, email=email)
                return user
            except User.DoesNotExist:
                return None

        except Exception:
            return None

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save()

        from .models import SecurityLog
        SecurityLog.objects.create(
            actor=user,
            action='PASSWORD_RESET',
            target=f"user:{user.id}",
            ip_address=self.context.get('request').META.get('REMOTE_ADDR'),
            user_agent=self.context.get('request').META.get('HTTP_USER_AGENT'),
            metadata={'method': 'reset_token'}
        )
        return user


# ============================================================================
# EMERGENCY 2FA SERIALIZERS – COMPATIBLE WITH EXISTING USER MODEL FIELDS (mfa_*)
# ============================================================================

class EmergencyTwoFactorSetupSerializer(serializers.Serializer):
    """
    Serializer for emergency 2FA setup validation.
    Checks if the user has recent suspicious activity before allowing setup.
    """
    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("User not found")

        user = request.user

        # Check if user has suspicious history in the last 30 days
        from .models import SecurityLog
        suspicious_count = SecurityLog.objects.filter(
            actor=None,
            target=user.email,
            action__in=['LOGIN_FAILED', 'SUSPICIOUS_LOGIN_DETECTED'],
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()

        if suspicious_count == 0:
            raise serializers.ValidationError(
                "No suspicious activity detected. Emergency 2FA not recommended."
            )

        return attrs


class EmergencyTwoFactorVerifySerializer(serializers.Serializer):
    """
    Serializer for emergency 2FA verification.
    Expects a verification token and the MFA code (TOTP or backup code).
    """
    verification_token = serializers.CharField(required=True)
    mfa_code = serializers.CharField(
        required=True,
        min_length=6,
        max_length=8,
        help_text="TOTP code from authenticator app or 8‑character backup code"
    )

    def validate(self, attrs):
        verification_token = attrs.get('verification_token')
        mfa_code = attrs.get('mfa_code')

        if not verification_token or not mfa_code:
            raise serializers.ValidationError("Both fields are required.")

        return attrs


# ============================================================================
# DEVICE MANAGEMENT SERIALIZERS (ADDED - Non-disruptive)
# ============================================================================

class UserSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for user sessions.
    """
    device_type = serializers.SerializerMethodField()
    is_current = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    
    class Meta:
        model = UserSession
        fields = [
            'id', 'device_fingerprint', 'device_type', 'is_current',
            'ip_address', 'location', 'user_agent',
            'last_activity', 'created_at', 'is_active'
        ]
        read_only_fields = fields
    
    def get_device_type(self, obj):
        from .utils.device_fingerprint import DeviceFingerprintGenerator
        return DeviceFingerprintGenerator.parse_platform(obj.user_agent)
    
    def get_is_current(self, obj):
        request = self.context.get('request')
        current_fingerprint = self.context.get('current_fingerprint')
        if current_fingerprint:
            return obj.device_fingerprint == current_fingerprint
        if request and hasattr(request, 'user'):
            return obj.device_fingerprint == request.user.hardware_fingerprint
        return False
    
    def get_location(self, obj):
        # Extend with your geolocation logic if available
        return "Unknown"


class DeviceChangeLogSerializer(serializers.ModelSerializer):
    """
    Serializer for device change history.
    """
    class Meta:
        model = DeviceChangeLog
        fields = [
            'old_fingerprint', 'new_fingerprint',
            'ip_address', 'user_agent',
            'verified', 'verified_at',
            'created_at'
        ]
        read_only_fields = fields