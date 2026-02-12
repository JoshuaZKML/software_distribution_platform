# FILE: /backend/config/celery.py (UPDATED)
import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Set the default Django settings module (keeping existing production setting)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings.production')

# Create Celery app instance
app = Celery('software_distribution_platform')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps (keeping lambda for compatibility)
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

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
}

# Configure task routing - merging with existing routing
app.conf.task_routes = {
    # Authentication tasks
    'backend.apps.accounts.tasks.*': {
        'queue': 'accounts'
    },
    # Email sending tasks
    'backend.apps.accounts.tasks.send_*': {
        'queue': 'emails'
    },
    # License tasks
    'backend.apps.licenses.tasks.*': {
        'queue': 'licenses'
    },
    # Product/software tasks
    'backend.apps.products.tasks.*': {
        'queue': 'products'
    },
    # Maintenance tasks
    'backend.apps.accounts.tasks.cleanup_*': {
        'queue': 'maintenance'
    },
}

# Task time limits (keeping existing values)
app.conf.task_time_limit = 300  # 5 minutes max
app.conf.task_soft_time_limit = 240  # 4 minutes soft limit

# Task result settings (adding new settings while keeping existing)
app.conf.result_expires = 3600  # Results expire after 1 hour
app.conf.result_backend = 'django-db'  # Store results in Django database

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
@app.task(bind=True, name='health_check')
def health_check(self):
    """Health check endpoint for monitoring."""
    return {
        'status': 'healthy',
        'timestamp': self.request.timestamp,
        'worker': self.request.hostname,
        'queues': list(app.conf.task_queues.keys() if hasattr(app.conf, 'task_queues') else ['default'])
    }