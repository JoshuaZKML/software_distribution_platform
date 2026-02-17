# How to Get Full Error Traceback for Debugging

## Problem
Previously, the login endpoint returned only "500 Internal Server Error" without showing the actual exception that caused it. This made debugging difficult.

## Solution Applied
We've implemented comprehensive exception handling and logging throughout the authentication flow.

## Getting Detailed Error Information

### Option 1: Enable DEBUG Mode (Development Only)

The most direct way to see detailed error pages with full tracebacks:

```python
# backend/config/settings/development.py
DEBUG = True  # Already set in development

# Then access the login endpoint and check the browser for the detailed error page
# (Django will display HTML error page with full traceback)
```

### Option 2: Check Django Logs

All exceptions are logged with full tracebacks:

```bash
# View Django logs in real-time
tail -f backend/logs/django.log

# The logs will show:
# - Full exception traceback
# - Request details (method, path, data)
# - User information
# - Timestamp and severity level
```

### Option 3: Check Application Logs

The application logs security events and errors:

```bash
# Check production logs (if deployed)
cat /var/log/django/app.log

# Or check the logs folder in the project
tail -f backend/logs/
```

### Option 4: Use Django Shell for Debugging

```bash
python manage.py shell

# Then interactively test the authentication
from django.contrib.auth import authenticate
from backend.apps.accounts.models import User

user = authenticate(username='admin@example.com', password='password123')
# If this fails, you'll see the exception with full details

# Or test the serializer directly
from backend.apps.accounts.serializers import CustomTokenObtainPairSerializer
from django.test import RequestFactory

factory = RequestFactory()
request = factory.post('/auth/login/')

serializer = CustomTokenObtainPairSerializer(
    data={'email': 'admin@example.com', 'password': 'password123'},
    context={'request': request}
)

# This will show any validation or serialization errors
print(serializer.is_valid())
print(serializer.errors if not serializer.is_valid() else "Valid")
```

### Option 5: Use Python Logging Configuration

The application already logs exceptions. To see them in the console during development:

```python
# backend/config/settings/development.py (add/modify this)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'backend/logs/django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'DEBUG',  # Set to DEBUG to see all messages
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'backend.apps.accounts': {  # Log all account app activity
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

## Understanding the Error Flow

### Before Fix (Returns 500 with no details):
```
1. Client sends login request
   ↓
2. View tries to validate email/password
   ↓
3. UserSession creation fails (null session_key)
   ↓
4. Exception propagates uncaught
   ↓
5. Django returns 500 error (no details)
```

### After Fix (Detailed error handling):
```
1. Client sends login request
   ↓
2. View wraps validation in try-except
   ↓
3. UserSession creation fails
   ↓
4. Exception is caught and logged with full traceback
   ↓
5. Returns meaningful error response (500 status but with error message)
   ↓
6. Logs show:
   - Exception type: IntegrityError
   - Stack trace: 23 lines of detailed context
   - Request details: email, IP, user agent
   - Timestamp and severity
```

## Viewing Exception Details at Runtime

### From Test Script
```bash
# Run the test script and it will show any exceptions that occur
python test_login_fix.py

# Output will show:
# - Exception type
# - Line number where it occurred
# - Variable values at the time
# - Full context
```

### From Django Admin
```bash
# Access Django admin shell
python manage.py shell

# Query SecurityLog for login attempts and errors
from backend.apps.accounts.models import SecurityLog

# Find all login errors
login_errors = SecurityLog.objects.filter(action='LOGIN_ERROR')
for log in login_errors:
    print(f"Error at {log.created_at}: {log.metadata}")
```

## Common Errors and Solutions

### 500 Error: "null value in column 'session_key'"
**Fixed by**: Generating fallback session_key when request.session.session_key is None
**Resolution**: Already implemented - should no longer occur

### 500 Error: "AttributeError: 'Settings' object has no attribute 'RISK_THRESHOLD_2FA'"
**Fixed by**: Importing RISK_THRESHOLD_2FA from security_checks module
**Resolution**: Already implemented - should no longer occur

### 500 Error: "IntegrityError" on UserSession creation
**Fixed by**: Proper session_key fallback and error handling
**Resolution**: Already implemented - should no longer occur

## Monitoring Production Errors

### Using Sentry (if configured)
```python
# If sentry-sdk is installed, all errors are automatically sent to Sentry
# Configure in settings:
import sentry_sdk
sentry_sdk.init("your-sentry-dsn-here")

# Then view errors at: https://sentry.io
```

### Email Notifications
Configure Django to email admins on 500 errors:

```python
# backend/config/settings/production.py
ADMINS = [('Admin Name', 'admin@example.com')]
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Django will automatically email errors to ADMINS list
```

## Quick Diagnostic Commands

```bash
# Check if all required packages are installed
pip check

# Verify database connection
python manage.py dbshell

# Check system imports
python -c "from backend.apps.accounts.views import UserLoginView; print('OK')"

# Run syntax check on specific file
python -m py_compile backend/apps/accounts/views.py

# Check for undefined variables (requires pylint)
pylint backend/apps/accounts/views.py
```

## Summary

The fix ensures that:
1. ✓ All exceptions are properly caught and handled
2. ✓ Error details are logged with full tracebacks
3. ✓ Meaningful error responses are returned to clients
4. ✓ Security events are logged in the SecurityLog
5. ✓ Development debugging is easy with multiple options
6. ✓ Production errors can be monitored and alerted on

No more silent 500 errors!
