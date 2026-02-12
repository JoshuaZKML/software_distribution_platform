# FILE: /backend/apps/accounts/utils/device_verification.py
import secrets
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

class DeviceVerificationManager:
    """
    Manage device verification using DeviceChangeLog.
    """
    
    @staticmethod
    def create_verification(user, new_fingerprint, request):
        """
        Create device verification record.
        Returns the DeviceChangeLog instance.
        """
        from ..models import DeviceChangeLog
        
        # Generate verification token
        token = secrets.token_urlsafe(32)
        verification_code = DeviceVerificationManager._generate_verification_code(
            str(user.id), new_fingerprint
        )
        
        # Create DeviceChangeLog entry
        device_log = DeviceChangeLog.objects.create(
            user=user,
            old_fingerprint=user.hardware_fingerprint,
            new_fingerprint=new_fingerprint,
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            verification_token=token,  # Store token for confirmation
            verified=False
        )
        
        # Store verification code in cache (expires in 24h)
        cache_key = f"device_verify_code:{token}"
        cache.set(cache_key, {
            'code': verification_code,
            'user_id': str(user.id),
            'new_fingerprint': new_fingerprint,
            'attempts': 0
        }, timeout=86400)
        
        return device_log, verification_code
    
    @staticmethod
    def verify_device(token, code):
        """
        Verify device using token and code.
        Updates DeviceChangeLog and user's fingerprint on success.
        """
        from ..models import DeviceChangeLog, User
        from django.core.exceptions import ObjectDoesNotExist
        
        cache_key = f"device_verify_code:{token}"
        data = cache.get(cache_key)
        
        if not data:
            return {'success': False, 'error': 'Invalid or expired verification token.'}
        
        # Check attempts
        if data['attempts'] >= 5:
            cache.delete(cache_key)
            return {'success': False, 'error': 'Too many failed attempts. Request new verification.'}
        
        # Increment attempts
        data['attempts'] += 1
        cache.set(cache_key, data, cache.ttl(cache_key))
        
        # Verify code
        if code != data['code']:
            return {
                'success': False,
                'error': 'Invalid verification code.',
                'attempts_remaining': 5 - data['attempts']
            }
        
        # Success – update DeviceChangeLog and user
        try:
            device_log = DeviceChangeLog.objects.get(
                verification_token=token,
                verified=False
            )
            device_log.verified = True
            device_log.verified_at = timezone.now()
            device_log.save()
            
            # Update user's hardware fingerprint
            user = User.objects.get(id=data['user_id'])
            user.hardware_fingerprint = data['new_fingerprint']
            user.last_device_change = timezone.now()
            user.save()
            
            # Clean up
            cache.delete(cache_key)
            
            return {
                'success': True,
                'user_id': data['user_id'],
                'device_fingerprint': data['new_fingerprint']
            }
            
        except ObjectDoesNotExist:
            return {'success': False, 'error': 'Verification record not found.'}
    
    @staticmethod
    def _generate_verification_code(user_id, fingerprint):
        """Generate 6-digit verification code."""
        import hashlib
        code_string = f"{user_id}|{fingerprint}|{settings.SECRET_KEY}"
        hash_obj = hashlib.sha256(code_string.encode())
        return hash_obj.hexdigest()[:6].upper()