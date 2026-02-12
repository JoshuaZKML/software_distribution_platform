# FILE: /backend/apps/accounts/views.py (FULLY UPDATED with Device Verification Views)
from rest_framework import status, generics, permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.utils import timezone
from django.conf import settings
import jwt
from datetime import datetime, timedelta
import secrets

from .serializers import (
    UserRegistrationSerializer, 
    CustomTokenObtainPairSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    ChangePasswordSerializer
)
from .models import User, UserSession, SecurityLog
from .permissions import IsSuperAdmin
from .security_checks import RiskAssessment  # must exist


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint (unchanged)."""
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


class UserLoginView(TokenObtainPairView):
    """
    Custom login view with device fingerprinting, security checks,
    and risk-based emergency 2FA.
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)

            # Risk assessment & emergency 2FA
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

                if (risk_level >= 6 and
                    user.mfa_emergency_only and
                    user.mfa_enabled and
                    user.mfa_secret):

                    payload = {
                        'user_id': str(user.id),
                        'purpose': 'emergency_2fa',
                        'risk_level': risk_level,
                        'reasons': reasons,
                        'exp': datetime.utcnow() + timedelta(minutes=10)
                    }
                    verification_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

                    SecurityLog.objects.create(
                        actor=user,
                        action='SUSPICIOUS_LOGIN_DETECTED',
                        target=f"user:{user.id}",
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT'),
                        metadata={
                            'risk_level': risk_level,
                            'reasons': reasons,
                            'requires_2fa': True,
                            'device_fingerprint': request.data.get('device_fingerprint', '')
                        }
                    )

                    return Response({
                        'success': False,
                        'requires_2fa': True,
                        'verification_token': verification_token,
                        'message': 'Suspicious activity detected. 2FA required.',
                        'risk_reasons': reasons,
                        'risk_level': risk_level
                    }, status=status.HTTP_200_OK)

            # Normal login
            return Response(serializer.validated_data, status=status.HTTP_200_OK)

        except serializers.ValidationError as e:
            if 'email' in request.data:
                self._log_failed_attempt(request)

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

    def _log_failed_attempt(self, request):
        SecurityLog.objects.create(
            actor=None,
            action='LOGIN_FAILED',
            target=request.data.get('email'),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT'),
            metadata={'data': request.data}
        )


class UserLogoutView(APIView):
    """Logout view (unchanged)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({'error': 'Refresh token required'}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()

            if hasattr(request, 'user'):
                UserSession.objects.filter(user=request.user, is_active=True).update(
                    is_active=False, last_activity=timezone.now()
                )

            return Response({'success': True, 'message': 'Successfully logged out'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Logout failed', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenRefreshView(TokenRefreshView):
    """Token refresh with user info (unchanged)."""
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            if request.user.is_authenticated:
                response.data['user'] = {
                    'id': str(request.user.id),
                    'email': request.user.email,
                    'role': request.user.role
                }
            return response
        except TokenError as e:
            return Response({'error': 'Token refresh failed', 'detail': str(e)}, status=status.HTTP_401_UNAUTHORIZED)


class PasswordResetRequestView(generics.GenericAPIView):
    """Password reset request (unchanged)."""
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
    """Password reset confirm (unchanged)."""
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
            return Response({'error': 'Password reset failed', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(generics.GenericAPIView):
    """Change password for authenticated users (unchanged)."""
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

            SecurityLog.objects.create(
                actor=user,
                action='PASSWORD_CHANGED',
                target=f"user:{user.id}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT'),
                metadata={'method': 'authenticated_change'}
            )

            UserSession.objects.filter(user=user, is_active=True).exclude(
                device_fingerprint=request.device_fingerprint
            ).update(is_active=False)

            return Response({'success': True, 'message': 'Password changed successfully.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': 'Password change failed', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# EMERGENCY 2FA VIEWS – COMPATIBLE WITH EXISTING USER MODEL FIELDS (mfa_*)
# ============================================================================

class EmergencyTwoFactorVerifyView(APIView):
    """
    Verify emergency 2FA code for suspicious login attempts.
    Expects `verification_token` and `mfa_code` in request body.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        verification_token = request.data.get('verification_token')
        mfa_code = request.data.get('mfa_code')  # TOTP or backup code

        if not verification_token or not mfa_code:
            return Response({
                'error': 'Verification token and MFA code are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = jwt.decode(verification_token, settings.SECRET_KEY, algorithms=['HS256'])
            if payload.get('purpose') != 'emergency_2fa':
                raise jwt.InvalidTokenError

            user = User.objects.get(id=payload['user_id'])

            # Verify using the model's method (works with TOTP or backup code)
            if not user.verify_mfa_code(mfa_code):
                SecurityLog.objects.create(
                    actor=None,
                    action='2FA_FAILED',
                    target=user.email,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT'),
                    metadata={
                        'verification_token': verification_token[:20] + '...',
                        'risk_level': payload.get('risk_level', 0)
                    }
                )
                return Response({'error': 'Invalid MFA code.'}, status=status.HTTP_400_BAD_REQUEST)

            # Success: generate fresh tokens
            refresh = RefreshToken.for_user(user)
            SecurityLog.objects.create(
                actor=user,
                action='2FA_VERIFIED',
                target=f"user:{user.id}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT'),
                metadata={
                    'risk_level': payload.get('risk_level', 0),
                    'reasons': payload.get('reasons', []),
                    'verification_type': 'emergency_mfa'
                }
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
    GET  → current status
    POST → enable and return QR URI + backup codes
    DELETE → disable (requires password confirmation)
    """
    permission_classes = [permissions.IsAuthenticated]

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
        if user.mfa_enabled:
            return Response({'error': 'MFA already enabled.'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate secret and backup codes (model method)
        secret = user.enable_emergency_mfa()

        return Response({
            'success': True,
            'mfa_enabled': True,
            'qr_code_uri': user.get_mfa_provisioning_uri(),
            'secret': secret,                # for manual entry
            'backup_codes': user.mfa_backup_codes,
            'message': 'Emergency 2FA enabled. Save backup codes securely.'
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

    def post(self, request):
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
# DEVICE VERIFICATION & MANAGEMENT VIEWS (ADDED - No disruption)
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
        SecurityLog.objects.create(
            actor_id=result['user_id'],
            action='DEVICE_VERIFIED',
            target=f"device:{result['device_fingerprint']}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT'),
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
        """Get list of trusted devices and active sessions."""
        from .models import UserSession, DeviceChangeLog
        from .serializers import UserSessionSerializer, DeviceChangeLogSerializer
        
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
        """Revoke specific session or all other sessions."""
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
                
                SecurityLog.objects.create(
                    actor=request.user,
                    action='SESSION_REVOKED',
                    target=f"session:{session_id}",
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT')
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
            # Revoke all other sessions
            current_fingerprint = request.user.hardware_fingerprint
            revoked_count = UserSession.objects.filter(
                user=request.user,
                is_active=True
            ).exclude(
                device_fingerprint=current_fingerprint
            ).update(is_active=False)
            
            SecurityLog.objects.create(
                actor=request.user,
                action='ALL_OTHER_SESSIONS_REVOKED',
                target=f"user:{request.user.id}",
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT'),
                metadata={'revoked_count': revoked_count}
            )
            
            return Response({
                'success': True,
                'message': f'{revoked_count} other sessions revoked.',
                'revoked_count': revoked_count
            }, status=status.HTTP_200_OK)