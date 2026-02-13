# FILE: /backend/config/celery.py (UPDATED - Production Hardened)
import os
from celery import Celery
from celery.schedules import crontab
from kombu import Queue
from django.conf import settings

# Set the default Django settings module (keeping existing production setting)
# NOTE: Hardcoding 'production' can cause issues in non‑production environments.
# For true environment separation, consider using environment variables or a
# settings module that dynamically loads the appropriate config.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings.production')

# Create Celery app instance
app = Celery('software_distribution_platform')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps (keeping lambda for compatibility)
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Explicitly define queues for routing and health checks
# This ensures health check returns accurate queue information and prevents
# tasks from falling into a non‑existent default queue.
app.conf.task_queues = (
    Queue('default'),      # Fallback queue for unmatched tasks
    Queue('accounts'),
    Queue('emails'),
    Queue('licenses'),
    Queue('products'),
    Queue('maintenance'),
)

# Default exchange/routing settings for safety
app.conf.task_default_queue = 'default'
app.conf.task_default_exchange = 'default'
app.conf.task_default_routing_key = 'default'

# Enforce JSON serialization for security and compatibility
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']

# Configure periodic tasks (Celery Beat schedule) - merging both configurations
app.conf.beat_schedule = {
    # Daily cleanup tasks
    'cleanup-expired-sessions-daily': {
        'task': 'backend.apps.accounts.tasks.cleanup_expired_sessions',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
        'options': {'queue': 'maintenance'}
    },
    
    # Weekly cleanup tasks
    'cleanup-failed-logins-weekly': {
        'task': 'backend.apps.accounts.tasks.cleanup_failed_login_attempts',
        'schedule': crontab(day_of_week='sunday', hour=4, minute=0),  # Sunday 4 AM
        'options': {'queue': 'maintenance'}
    },
    
    # Send weekly account summaries every Monday at 9 AM (from existing config)
    'send-weekly-summaries': {
        'task': 'backend.apps.accounts.tasks.send_account_summary_email',
        'schedule': crontab(day_of_week='monday', hour=9, minute=0),
        'args': (None,),  # Will be populated by a management command
        'options': {'queue': 'emails'}
    },
    
    # Email queue processing (keeping more frequent schedule from existing - every 5 minutes)
    'process-email-queue': {
        'task': 'backend.apps.accounts.tasks.process_email_queue',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes (as in existing)
        'options': {'queue': 'emails'}
    },
    
    # Check for expiring licenses (daily at 9 AM) - new from update
    'check-expiring-licenses': {
        'task': 'backend.apps.licenses.tasks.check_expiring_licenses',
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
        'args': (7,),  # 7 days warning
        'options': {'queue': 'licenses'}
    },
    
    # Cleanup expired licenses (daily at midnight) - new from update
    'cleanup-expired-licenses': {
        'task': 'backend.apps.licenses.tasks.cleanup_expired_licenses',
        'schedule': crontab(hour=0, minute=0),  # Midnight
        'options': {'queue': 'licenses'}
    },

    # Send license expiry reminders daily at 8 AM (added 2026‑02‑13)
    # FIXED: task path now matches the full dotted convention used elsewhere.
    'send-license-expiry-reminders': {
        'task': 'backend.apps.licenses.tasks.send_license_expiry_reminders',
        'schedule': crontab(hour=8, minute=0),  # 8 AM daily
        'options': {'queue': 'licenses'}
    },
}

# Configure task routing - merging with existing routing
# Order matters: more specific patterns must come before generic ones.
app.conf.task_routes = {
    # Email sending tasks (specific first)
    'backend.apps.accounts.tasks.send_*': {
        'queue': 'emails'
    },
    # Maintenance tasks (specific)
    'backend.apps.accounts.tasks.cleanup_*': {
        'queue': 'maintenance'
    },
    # Generic accounts tasks
    'backend.apps.accounts.tasks.*': {
        'queue': 'accounts'
    },
    # License tasks
    'backend.apps.licenses.tasks.*': {
        'queue': 'licenses'
    },
    # Product/software tasks
    'backend.apps.products.tasks.*': {
        'queue': 'products'
    },
    # All other tasks fall back to default queue (handled by task_default_queue)
}

# Task time limits (keeping existing values)
app.conf.task_time_limit = 300  # 5 minutes max
app.conf.task_soft_time_limit = 240  # 4 minutes soft limit

# Task result settings (adding new settings while keeping existing)
app.conf.result_expires = 3600  # Results expire after 1 hour
app.conf.result_backend = 'django-db'  # Store results in Django database
# NOTE: 'django-db' result backend may become a bottleneck at scale.
# For high throughput, consider Redis or RPC backend.

# Worker settings (adding new settings while keeping existing)
app.conf.worker_prefetch_multiplier = 1  # Process one task at a time
app.conf.worker_max_tasks_per_child = 1000  # Keep existing higher value for compatibility
app.conf.worker_max_memory_per_child = 200000  # 200MB memory limit (new)

# Retry settings (new from update)
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True

# Redis settings (new from update)
app.conf.broker_transport_options = {
    'visibility_timeout': 3600,  # 1 hour
    'socket_connect_timeout': 5,
    'retry_on_timeout': True,
}

# Debug task (enhanced version with ignore_result parameter)
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to test Celery is working."""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'

# Health check task (new from update)
# Now uses the explicitly defined task_queues to return real data.
@app.task(bind=True, name='health_check')
def health_check(self):
    """Health check endpoint for monitoring."""
    return {
        'status': 'healthy',
        'timestamp': self.request.timestamp,
        'worker': self.request.hostname,
        'queues': [q.name for q in app.conf.task_queues] if hasattr(app.conf, 'task_queues') else ['default']
    }