# FILE: /test_email_flow.py
import os
import django
from django.core.mail import send_mail

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings.development')
django.setup()

from backend.apps.accounts.models import User
from backend.apps.accounts.tasks import (
    send_verification_email,
    send_password_reset_email,
    send_welcome_email
)

def test_email_system():
    """Test the email system end-to-end."""
    
    # Create test user
    user, created = User.objects.get_or_create(
        email='test@example.com',
        defaults={
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'testpass123'
        }
    )
    
    print(f"Testing with user: {user.email}")
    
    # Test 1: Send verification email
    print("\n1. Testing verification email...")
    try:
        result = send_verification_email.delay(str(user.id))
        print(f"   Task queued: {result.id}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Send password reset email
    print("\n2. Testing password reset email...")
    try:
        result = send_password_reset_email.delay(str(user.id), 'test_reset_token_123')
        print(f"   Task queued: {result.id}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Send welcome email (only if verified)
    print("\n3. Testing welcome email...")
    user.is_verified = True
    user.save()
    try:
        result = send_welcome_email.delay(str(user.id))
        print(f"   Task queued: {result.id}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n✅ Email system test completed!")
    print("Check the Celery worker logs to see if tasks were executed successfully.")

if __name__ == '__main__':
    test_email_system()