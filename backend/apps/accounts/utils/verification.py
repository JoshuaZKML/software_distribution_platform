# FILE: /backend/apps/accounts/utils/verification.py
import uuid
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from ..models import User

class EmailVerificationToken:
    """
    Generate and validate email verification tokens.
    """
    
    @staticmethod
    def generate_token(user_id, email):
        """
        Generate a secure verification token.
        Format: user_id|email|timestamp|random_string
        """
        import hashlib
        import secrets
        
        timestamp = str(int(timezone.now().timestamp()))
        random_string = secrets.token_urlsafe(16)
        
        token_string = f"{user_id}|{email}|{timestamp}|{random_string}"
        
        # Create signature
        signature = hashlib.sha256(
            f"{token_string}{settings.SECRET_KEY}".encode()
        ).hexdigest()[:16]
        
        # Combine token with signature
        full_token = f"{token_string}|{signature}"
        
        # Encode for URL safety
        import base64
        encoded_token = base64.urlsafe_b64encode(full_token.encode()).decode()
        
        return encoded_token
    
    @staticmethod
    def validate_token(token, max_age_hours=24):
        """
        Validate verification token and return user if valid.
        """
        try:
            import base64
            import hashlib
            from django.utils import timezone
            
            # Decode token
            decoded_token = base64.urlsafe_b64decode(token.encode()).decode()
            
            # Split components
            parts = decoded_token.split('|')
            if len(parts) != 5:
                return None
            
            user_id, email, timestamp, random_string, signature = parts
            
            # Verify signature
            expected_signature = hashlib.sha256(
                f"{user_id}|{email}|{timestamp}|{random_string}{settings.SECRET_KEY}".encode()
            ).hexdigest()[:16]
            
            if signature != expected_signature:
                return None
            
            # Check token age
            token_time = datetime.fromtimestamp(int(timestamp))
            if timezone.now() - token_time > timedelta(hours=max_age_hours):
                return None
            
            # Get user
            try:
                user = User.objects.get(id=user_id, email=email)
                return user
            except User.DoesNotExist:
                return None
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Token validation error: {str(e)}")
            return None