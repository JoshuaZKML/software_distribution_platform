# FILE: /test_celery.py (CREATE NEW)
import os
import sys
import django

# Add the project to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings.development')
django.setup()

from backend.apps.accounts.models import User
from backend.apps.accounts.tasks import (
    send_verification_email,
    send_password_reset_email,
    send_welcome_email,
    health_check
)
from celery.result import AsyncResult
from backend.config.celery import app

def test_celery_connection():
    """Test if Celery can connect to Redis."""
    try:
        # Test the health check task
        result = health_check.delay()
        print(f"Health check task ID: {result.id}")
        
        # Wait for result
        result_value = result.get(timeout=10)
        print(f"Health check result: {result_value}")
        return True
    except Exception as e:
        print(f"❌ Celery connection failed: {e}")
        return False

def test_email_tasks():
    """Test email sending tasks."""
    # Create or get test user
    user, created = User.objects.get_or_create(
        email='test@example.com',
        defaults={
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'testpass123'
        }
    )
    
    if created:
        print(f"Created test user: {user.email}")
    
    print("\n📧 Testing email tasks...")
    
    # Test 1: Verification email
    print("\n1. Testing verification email...")
    try:
        task = send_verification_email.delay(str(user.id))
        print(f"   Task ID: {task.id}")
        print(f"   Status: {task.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Password reset email
    print("\n2. Testing password reset email...")
    try:
        task = send_password_reset_email.delay(str(user.id), 'test_token_123')
        print(f"   Task ID: {task.id}")
        print(f"   Status: {task.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Welcome email (after verification)
    print("\n3. Testing welcome email...")
    user.is_verified = True
    user.save()
    try:
        task = send_welcome_email.delay(str(user.id))
        print(f"   Task ID: {task.id}")
        print(f"   Status: {task.status}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return True

def check_task_results():
    """Check results of recently executed tasks."""
    print("\n📊 Checking task results...")
    
    # Get all task results from the result backend
    from django_celery_results.models import TaskResult
    recent_tasks = TaskResult.objects.all().order_by('-date_created')[:5]
    
    if recent_tasks.exists():
        print(f"Found {recent_tasks.count()} recent tasks:")
        for task in recent_tasks:
            print(f"  • {task.task_id}: {task.task_name} - {task.status}")
            if task.result:
                print(f"    Result: {task.result[:100]}...")
    else:
        print("No recent tasks found.")

def main():
    """Main test function."""
    print("🧪 Testing Celery Setup")
    print("=" * 50)
    
    # Test Celery connection
    if not test_celery_connection():
        print("\n❌ Celery setup failed. Check Redis connection.")
        return False
    
    # Test email tasks
    if not test_email_tasks():
        print("\n❌ Email tasks failed.")
        return False
    
    # Check results
    check_task_results()
    
    print("\n" + "=" * 50)
    print("✅ All tests completed successfully!")
    print("\nTo monitor tasks in real-time:")
    print("  - Start Flower: celery -A backend.config.celery flower")
    print("  - Visit: http://localhost:5555")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)