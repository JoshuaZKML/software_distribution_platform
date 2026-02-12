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

# FILE: /backend/apps/accounts/tasks.py (Celery tasks)
from celery import shared_task
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from .utils.verification import EmailVerificationToken

@shared_task
def send_verification_email(user_id):
    """
    Send verification email asynchronously.
    """
    from .models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        # Generate verification token
        token = EmailVerificationToken.generate_token(str(user.id), user.email)
        
        # Build verification URL
        verification_url = f"{settings.FRONTEND_URL}/verify-email/{token}"
        
        # Email content
        subject = "Verify Your Email - Software Distribution Platform"
        context = {
            'user': user,
            'verification_url': verification_url,
            'support_email': settings.SUPPORT_EMAIL,
        }
        
        html_message = render_to_string('accounts/email/verification.html', context)
        text_message = render_to_string('accounts/email/verification.txt', context)
        
        # Send email
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            reply_to=[settings.SUPPORT_EMAIL],
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)
        
        return f"Verification email sent to {user.email}"
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send verification email: {str(e)}")
        raise e

# FILE: /backend/apps/accounts/views.py (ADD VERIFICATION VIEW)
class VerifyEmailView(APIView):
    """
    Verify email using token from verification email.
    """
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, token):
        from .utils.verification import EmailVerificationToken
        
        user = EmailVerificationToken.validate_token(token)
        
        if user:
            # Mark user as verified
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