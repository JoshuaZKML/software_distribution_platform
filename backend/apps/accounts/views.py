# FILE: /backend/apps/accounts/views.py
"""
Authentication views with enhanced security hardening.
Non‑disruptive: all existing endpoints and response structures preserved,
except sensitive data is no longer leaked and replay attacks are mitigated.
"""
import logging
import secrets
from datetime import datetime, timedelta

import jwt
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from rest_framework import generics, permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import SecurityLog, User, UserSession
from .permissions import IsSuperAdmin
from .security_checks import RiskAssessment
from .serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserRegistrationSerializer,
    NotificationPreferencesSerializer,
    # ===== NEW: Emergency 2FA serializers =====
    EmergencyTwoFactorSetupSerializer,
    EmergencyTwoFactorVerifySerializer,
    RegenerateBackupCodesSerializer,
)
from .utils.verification import EmailVerificationToken

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Helper functions – non‑disruptive extraction
# ----------------------------------------------------------------------
def _get_client_ip(request):
    """Extract real client IP, respecting proxies."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _log_security_event(actor, action, target, request, metadata=None):
    """Centralised, safe security logging – prevents sensitive data leakage."""
    # Never log the entire request.data – copy only safe fields
    safe_metadata = metadata or {}
    if 'password' in safe_metadata:
        safe_metadata['password'] = '[REDACTED]'
    if 'new_password' in safe_metadata:
        safe_metadata['new_password'] = '[REDACTED]'
    if 'current_password' in safe_metadata:
        safe_metadata['current_password'] = '[REDACTED]'
    if 'confirm_password' in safe_metadata:
        safe_metadata['confirm_password'] = '[REDACTED]'

    SecurityLog.objects.create(
        actor=actor,
        action=action,
        target=target,
        ip_address=_get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata=safe_metadata
    )


# ----------------------------------------------------------------------
# User registration (unchanged except import)
# ----------------------------------------------------------------------
class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint."""
    serializer_class = UserRegistrationSerializer
    queryset = User.objects.all()

    def get_permissions(self):
        if self.request.method == 'POST':
            role = self.request.data.get('role', User.Role.USER)
            if role in [User.Role.ADMIN, User.Role.SUPER_ADMIN]:
                return [permissions.IsAuthenticated(), IsSuperAdmin()]
        return [permissions.AllowAny()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response_data = {
            'id': str(user.id),
            'email': user.email,
            'role': user.role,
            'message': 'User registered successfully. Please check your email for verification.',
            'requires_verification': not user.is_verified
        }
        if hasattr(user, 'admin_profile'):
            response_data['admin_profile'] = {
                'can_manage_users': user.admin_profile.can_manage_users,
                'can_manage_licenses': user.admin_profile.can_manage_licenses,
            }
        return Response(response_data, status=status.HTTP_201_CREATED)


# ----------------------------------------------------------------------
# Login – hardened, risk details hidden, replay protection added
# ----------------------------------------------------------------------
class UserLoginView(TokenObtainPairView):
    """
    Custom login view with device fingerprinting, security checks,
    and risk‑based emergency 2FA. No longer returns risk reasons to client.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)

            user = getattr(serializer, 'user', None)
            if not user and 'email' in request.data:
                try:
                    user = User.objects.get(email=request.data['email'])
                except User.DoesNotExist:
                    user = None

            if user and user.is_active:
                risk_level, reasons = RiskAssessment.check_suspicious_behavior(
                    user=user,
                    request=request,
                    context=serializer.validated_data.get('context', {})
                )

                if (risk_level >= settings.RISK_THRESHOLD_2FA and
                    user.mfa_emergency_only and
                    user.mfa_enabled and
                    user.mfa_secret):

                    # Generate a single‑use jti and store in cache
                    jti = secrets.token_urlsafe(16)
                    cache_key = f"emergency_2fa:{jti}"
                    payload = {
                        'user_id': str(user.id),
                        'purpose': 'emergency_2fa',
                        'risk_level': risk_level,
                        'jti': jti,
                        'exp': datetime.utcnow() + timedelta(minutes=10)
                    }
                    verification_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
                    # Store token ID in cache with same expiry
                    cache.set(cache_key, user.id, 600)

                    _log_security_event(
                        actor=user,
                        action='SUSPICIOUS_LOGIN_DETECTED',
                        target=f"user:{user.id}",
                        request=request,
                        metadata={
                            'risk_level': risk_level,
                            'requires_2fa': True,
                            'device_fingerprint': request.data.get('device_fingerprint', '')
                        }
                    )

                    # Return only generic message – no risk details
                    return Response({
                        'success': False,
                        'requires_2fa': True,
                        'verification_token': verification_token,
                        'message': 'Suspicious activity detected. 2FA required.'
                    }, status=status.HTTP_200_OK)

            # Normal login
            return Response(serializer.validated_data, status=status.HTTP_200_OK)

        except serializers.ValidationError as e:
            # Safely log failed attempt without full request.data
            if 'email' in request.data:
                _log_security_event(
                    actor=None,
                    action='LOGIN_FAILED',
                    target=request.data.get('email', 'unknown'),
                    request=request,
                    metadata={'email': request.data.get('email')}
                )

            if 'device_change' in e.detail:
                return Response({
                    'success': False,
                    'requires_device_verification': True,
                    'message': e.detail['message']
                }, status=status.HTTP_200_OK)

            return Response({
                'success': False,
                'error': 'Authentication failed',
                'details': e.detail
            }, status=status.HTTP_401_UNAUTHORIZED)


# ----------------------------------------------------------------------
# Logout (unchanged)
# ----------------------------------------------------------------------
class UserLogoutView(APIView):
    """Logout view."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({'error': 'Refresh token required'}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()

            UserSession.objects.filter(user=request.user, is_active=True).update(
                is_active=False, last_activity=timezone.now()
            )

            return Response({'success': True, 'message': 'Successfully logged out'}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Logout failed")
            return Response({'error': 'Logout failed', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ----------------------------------------------------------------------
# Token refresh (unchanged)
# ----------------------------------------------------------------------
class CustomTokenRefreshView(TokenRefreshView):
    """Token refresh with user info."""
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            # Safely obtain user from refresh token
            refresh_token = request.data.get('refresh')
            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    user_id = token['user_id']
                    user = User.objects.get(id=user_id)
                    response.data['user'] = {
                        'id': str(user.id),
                        'email': user.email,
                        'role': user.role
                    }
                except Exception:
                    # User not found or token invalid – ignore
                    pass
            return response
        except TokenError as e:
            return Response({'error': 'Token refresh failed', 'detail': str(e)}, status=status.HTTP_401_UNAUTHORIZED)


# ----------------------------------------------------------------------
# Password reset (unchanged)
# ----------------------------------------------------------------------
class PasswordResetRequestView(generics.GenericAPIView):
    """Password reset request."""
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            token = serializer.create_reset_token(user)
            from .tasks import send_password_reset_email
            send_password_reset_email.delay(user.id, token)
        except User.DoesNotExist:
            pass
        return Response({
            'success': True,
            'message': 'If an account exists with this email, you will receive a password reset link.'
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmView(generics.GenericAPIView):
    """Password reset confirm."""
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
            UserSession.objects.filter(user=user, is_active=True).update(is_active=False)
            return Response({
                'success': True,
                'message': 'Password has been reset successfully. You can now log in with your new password.'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Password reset failed")
            return Response({'error': 'Password reset failed', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ----------------------------------------------------------------------
# Change password – hardened session exclusion
# ----------------------------------------------------------------------
class ChangePasswordView(generics.GenericAPIView):
    """Change password for authenticated users."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            user = request.user
            if not user.check_password(serializer.validated_data['current_password']):
                return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)

            user.set_password(serializer.validated_data['new_password'])
            user.save()

            _log_security_event(
                actor=user,
                action='PASSWORD_CHANGED',
                target=f"user:{user.id}",
                request=request,
                metadata={'method': 'authenticated_change'}
            )

            # Revoke all other active sessions – but keep the current one
            current_session_id = None
            if hasattr(request, 'session') and request.session.session_key:
                current_session_id = request.session.session_key
            qs = UserSession.objects.filter(user=user, is_active=True)
            if current_session_id:
                qs = qs.exclude(session_key=current_session_id)
            else:
                # Fallback: use device fingerprint if session key not available
                current_fingerprint = request.data.get('device_fingerprint', '')
                if current_fingerprint:
                    qs = qs.exclude(device_fingerprint=current_fingerprint)
            qs.update(is_active=False)

            return Response({'success': True, 'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Password change failed")
            return Response({'error': 'Password change failed', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# EMERGENCY 2FA VIEWS – HARDENED (UPDATED WITH SERIALIZERS)
# ============================================================================

class EmergencyTwoFactorVerifyView(APIView):
    """
    Verify emergency 2FA code for suspicious login attempts.
    - Replay protection: verification_token is single‑use (jti cached).
    - No sensitive data returned.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = EmergencyTwoFactorVerifySerializer   # <-- ADDED

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        verification_token = serializer.validated_data['verification_token']
        mfa_code = serializer.validated_data['mfa_code']

        try:
            payload = jwt.decode(verification_token, settings.SECRET_KEY, algorithms=['HS256'])
            if payload.get('purpose') != 'emergency_2fa':
                raise jwt.InvalidTokenError

            jti = payload.get('jti')
            if not jti:
                raise jwt.InvalidTokenError("Missing jti")

            # Single‑use enforcement
            cache_key = f"emergency_2fa:{jti}"
            if cache.get(cache_key) is None:
                return Response({'error': 'Verification token expired or already used.'}, status=status.HTTP_400_BAD_REQUEST)
            # Delete immediately to prevent replay
            cache.delete(cache_key)

            user = User.objects.get(id=payload['user_id'])

            if not user.verify_mfa_code(mfa_code):
                _log_security_event(
                    actor=None,
                    action='2FA_FAILED',
                    target=user.email,
                    request=request,
                    metadata={'verification_type': 'emergency_mfa'}
                )
                return Response({'error': 'Invalid MFA code.'}, status=status.HTTP_400_BAD_REQUEST)

            # Success – generate fresh tokens
            refresh = RefreshToken.for_user(user)
            _log_security_event(
                actor=user,
                action='2FA_VERIFIED',
                target=f"user:{user.id}",
                request=request,
                metadata={'verification_type': 'emergency_mfa'}
            )

            return Response({
                'success': True,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'role': user.role
                },
                'message': 'MFA verified successfully.'
            }, status=status.HTTP_200_OK)

        except jwt.ExpiredSignatureError:
            return Response({'error': 'Verification token expired.'}, status=status.HTTP_400_BAD_REQUEST)
        except (jwt.InvalidTokenError, User.DoesNotExist):
            return Response({'error': 'Invalid verification token.'}, status=status.HTTP_400_BAD_REQUEST)


class EmergencyTwoFactorSetupView(APIView):
    """
    Setup emergency 2FA (TOTP) for the authenticated user.
    - Now requires a verification step: after generating secret, user must
      provide a valid TOTP code before MFA is enabled.
    - Backward‑compatible: POST with {'code': '123456'} after initial POST.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = EmergencyTwoFactorSetupSerializer   # <-- ADDED

    def get(self, request):
        user = request.user
        return Response({
            'mfa_enabled': user.mfa_enabled,
            'mfa_emergency_only': user.mfa_emergency_only,
            'backup_codes_remaining': len(user.mfa_backup_codes) if user.mfa_backup_codes else 0,
            'last_used': user.mfa_last_used
        })

    def post(self, request):
        user = request.user

        # If MFA already enabled, return error
        if user.mfa_enabled:
            return Response({'error': 'MFA already enabled.'}, status=status.HTTP_400_BAD_REQUEST)

        # For the verification step, we don't use the serializer because we need to check the code against user.
        # But we can still run the serializer for the initial POST (no code) to perform the suspicious activity check.
        if 'code' not in request.data:
            # First step: validate that the user has suspicious activity
            serializer = self.serializer_class(data={}, context={'request': request})
            serializer.is_valid(raise_exception=True)

            # Generate secret and backup codes (but do NOT enable yet)
            secret = user.enable_emergency_mfa()  # This also sets mfa_enabled=False? We'll modify model method later.
            # For now, we'll manually set mfa_enabled=False after generation.
            user.mfa_enabled = False
            user.save(update_fields=['mfa_enabled'])

            return Response({
                'success': True,
                'requires_verification': True,
                'qr_code_uri': user.get_mfa_provisioning_uri(),
                'secret': user.mfa_secret,  # for manual entry
                'message': 'Scan the QR code with your authenticator app, then verify with a code to enable MFA.'
            })

        # Second step: verify code and activate MFA
        if not user.mfa_secret:
            return Response({'error': 'MFA not initialized. Please start setup first.'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.verify_mfa_code(request.data['code']):
            return Response({'error': 'Invalid verification code.'}, status=status.HTTP_400_BAD_REQUEST)

        # Activate MFA (already enabled, but ensure flag is set)
        user.mfa_enabled = True
        user.mfa_emergency_only = True
        user.save()

        return Response({
            'success': True,
            'mfa_enabled': True,
            'backup_codes': user.mfa_backup_codes,
            'message': 'MFA enabled successfully. Save your backup codes.'
        })

    def delete(self, request):
        user = request.user
        password = request.data.get('password')
        if not password or not user.check_password(password):
            return Response({'error': 'Password required to disable MFA.'}, status=status.HTTP_400_BAD_REQUEST)

        user.disable_mfa()
        return Response({'success': True, 'message': 'Emergency 2FA disabled.'})


class RegenerateBackupCodesView(APIView):
    """
    Regenerate emergency backup codes.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RegenerateBackupCodesSerializer   # <-- ADDED

    def post(self, request):
        # The serializer does not expect any input, but we still use it to validate (trivial)
        serializer = self.serializer_class(data={})
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.mfa_enabled:
            return Response({'error': 'MFA is not enabled.'}, status=status.HTTP_400_BAD_REQUEST)

        new_codes = user.regenerate_backup_codes()
        return Response({
            'success': True,
            'backup_codes': new_codes,
            'message': 'Backup codes regenerated. Old codes are invalid.'
        })


# ============================================================================
# DEVICE VERIFICATION & MANAGEMENT VIEWS
# ============================================================================

class DeviceVerificationConfirmView(APIView):
    """
    Confirm device verification using token and code from email.
    Completes the device change flow.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from .utils.device_verification import DeviceVerificationManager

        token = request.data.get('token')
        code = request.data.get('code')

        if not token or not code:
            return Response({
                'error': 'Token and verification code are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        result = DeviceVerificationManager.verify_device(token, code)

        if not result['success']:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        # Log successful verification
        _log_security_event(
            actor_id=result['user_id'],
            action='DEVICE_VERIFIED',
            target=f"device:{result['device_fingerprint']}",
            request=request,
            metadata={'verification_method': 'email'}
        )

        return Response({
            'success': True,
            'message': 'Device verified successfully. You can now log in.'
        }, status=status.HTTP_200_OK)


class DeviceManagementView(APIView):
    """
    Manage user's trusted devices and active sessions.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import DeviceChangeLog, UserSession
        from .serializers import DeviceChangeLogSerializer, UserSessionSerializer

        # Active sessions (only the ones with verified devices)
        active_sessions = UserSession.objects.filter(
            user=request.user,
            is_active=True
        ).order_by('-last_activity')

        # Device change history (verified devices only)
        device_history = DeviceChangeLog.objects.filter(
            user=request.user,
            verified=True
        ).order_by('-verified_at')[:20]

        # Current device fingerprint
        current_fingerprint = request.user.hardware_fingerprint

        sessions_data = UserSessionSerializer(
            active_sessions,
            many=True,
            context={'request': request, 'current_fingerprint': current_fingerprint}
        ).data

        history_data = DeviceChangeLogSerializer(device_history, many=True).data

        return Response({
            'current_device_fingerprint': current_fingerprint,
            'last_device_change': request.user.last_device_change,
            'active_sessions': sessions_data,
            'device_history': history_data
        }, status=status.HTTP_200_OK)

    def delete(self, request, session_id=None):
        from .models import UserSession

        if session_id:
            # Revoke specific session
            try:
                session = UserSession.objects.get(
                    id=session_id,
                    user=request.user,
                    is_active=True
                )
                session.is_active = False
                session.save()

                _log_security_event(
                    actor=request.user,
                    action='SESSION_REVOKED',
                    target=f"session:{session_id}",
                    request=request
                )

                return Response({
                    'success': True,
                    'message': 'Session revoked successfully.'
                }, status=status.HTTP_200_OK)

            except UserSession.DoesNotExist:
                return Response({
                    'error': 'Active session not found.'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Revoke all other sessions – use session key if available, else fingerprint
            current_session_key = request.session.session_key if hasattr(request, 'session') else None
            qs = UserSession.objects.filter(user=request.user, is_active=True)
            if current_session_key:
                qs = qs.exclude(session_key=current_session_key)
            else:
                current_fingerprint = request.user.hardware_fingerprint
                qs = qs.exclude(device_fingerprint=current_fingerprint)

            revoked_count = qs.update(is_active=False)

            _log_security_event(
                actor=request.user,
                action='ALL_OTHER_SESSIONS_REVOKED',
                target=f"user:{request.user.id}",
                request=request,
                metadata={'revoked_count': revoked_count}
            )

            return Response({
                'success': True,
                'message': f'{revoked_count} other sessions revoked.',
                'revoked_count': revoked_count
            }, status=status.HTTP_200_OK)


# ============================================================================
# NOTIFICATION PREFERENCES VIEW (ADDED – production‑ready)
# ============================================================================

class NotificationPreferencesView(APIView):
    """
    Get or update notification preferences for the authenticated user.
    Uses GET to retrieve current preferences and POST to update (merge).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return the user's current notification preferences."""
        prefs = request.user.notification_preferences or {}
        serializer = NotificationPreferencesSerializer(data=prefs)
        serializer.is_valid(raise_exception=True)  # Validate stored data (should always be valid)
        return Response(serializer.data)

    def post(self, request):
        """
        Update notification preferences.
        Merges incoming data with existing preferences, validates the combined result,
        and saves if valid. Returns the updated preferences.
        """
        user = request.user
        current_prefs = user.notification_preferences or {}

        # Merge incoming data with current preferences
        merged_prefs = current_prefs.copy()
        merged_prefs.update(request.data)

        # Validate the merged preferences using the serializer
        serializer = NotificationPreferencesSerializer(data=merged_prefs)
        serializer.is_valid(raise_exception=True)

        # Save the validated, merged preferences
        user.notification_preferences = serializer.validated_data
        try:
            user.save(update_fields=['notification_preferences'])
        except Exception as e:
            logger.exception("Failed to save notification preferences for user %s", user.id)
            return Response(
                {'error': 'Failed to save preferences. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Log the change for audit (optional)
        _log_security_event(
            actor=user,
            action='NOTIFICATION_PREFERENCES_UPDATED',
            target=f"user:{user.id}",
            request=request,
            metadata={'changed_fields': list(request.data.keys())}
        )

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# ============================================================================
# UNSUBSCRIBE ENDPOINT (adapted to accept single token)
# ============================================================================

class UnsubscribeThrottle(UserRateThrottle):
    rate = '5/min'


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([UnsubscribeThrottle])
def unsubscribe(request):
    """
    Unsubscribe user from marketing emails using a signed token.
    The token is generated by the `get_unsubscribe_token` method on the User model
    and is expected as a single combined 'token' parameter containing uid and token
    separated by a slash.
    """
    combined_token = request.data.get('token')
    if not combined_token:
        return Response({'error': 'Missing token'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uid_b64, token_part = combined_token.split('/', 1)
        user_id = force_str(urlsafe_base64_decode(uid_b64))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, token_part):
        return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

    if user.unsubscribed:
        return Response({'status': 'already_unsubscribed'}, status=status.HTTP_200_OK)

    # Log the unsubscribe event for audit purposes
    _log_security_event(
        actor=user,
        action='UNSUBSCRIBED',
        target=f"user:{user.id}",
        request=request,
        metadata={'method': 'token_link'}
    )

    user.unsubscribed = True
    user.save(update_fields=['unsubscribed'])

    return Response({'status': 'unsubscribed'}, status=status.HTTP_200_OK)


# ============================================================================
# VERIFY EMAIL VIEW (moved from utils/verification.py)
# ============================================================================

class VerifyEmailView(APIView):
    """
    Verify email using token from verification email.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        user = EmailVerificationToken.validate_token(token)

        if user:
            user.is_verified = True
            user.save()

            return Response({
                'success': True,
                'message': 'Email verified successfully. You can now log in.',
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'role': user.role
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Invalid or expired verification token.'
            }, status=status.HTTP_400_BAD_REQUEST)