import os
import sys
import logging
import psutil
from datetime import datetime

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.core.cache import cache
from django.core.mail import send_mail

from celery import current_app as celery_app
from redis import Redis
from redis.exceptions import RedisError

from .permissions import IsSuperAdmin  # Kept for consistency, not directly used

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Step 1 – Reusable Health Data Collector (single source of truth)
# ----------------------------------------------------------------------
def collect_health_data(request=None):
    """
    Collect all health component data.
    Returns a dictionary with 'components', 'overall_status', 'summary', etc.
    This is the single source of truth for both JSON and HTML endpoints.
    The status logic exactly matches the original super_admin_health_check.
    """
    start_time = datetime.now()
    components = {}
    overall_status = 'ok'

    # ------------------------------------------------------------
    # 1. DATABASE
    # ------------------------------------------------------------
    db_status = 'ok'
    db_details = {}
    try:
        db_conn = connections['default']
        with db_conn.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        db_details['connection'] = 'ok'
        db_details['backend'] = db_conn.vendor
    except OperationalError as e:
        db_status = 'unavailable'
        db_details['error'] = str(e)
        overall_status = 'degraded'
        logger.exception('Database health check failed')
    components['database'] = {'status': db_status, 'details': db_details}

    # ------------------------------------------------------------
    # 2. REDIS CACHE (graceful degradation – overall status only degrades if IGNORE_EXCEPTIONS=True)
    # ------------------------------------------------------------
    redis_status = 'ok'
    redis_details = {}
    redis_client = None
    try:
        redis_url = settings.REDIS_URL
        redis_client = Redis.from_url(
            redis_url,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        redis_client.ping()
        redis_details['ping'] = 'pong'
        redis_details['version'] = redis_client.info().get('redis_version', 'unknown')
        redis_details['used_memory_human'] = redis_client.info().get('used_memory_human', 'unknown')
    except Exception as e:
        ignore_exceptions = settings.CACHES['default']['OPTIONS'].get('IGNORE_EXCEPTIONS', False)
        redis_status = 'unavailable' if not ignore_exceptions else 'degraded'
        redis_details['error'] = str(e)
        redis_details['ignore_exceptions'] = ignore_exceptions
        if ignore_exceptions:
            overall_status = 'degraded'  # only degrade when IGNORE_EXCEPTIONS=True (original behaviour)
        logger.warning(f'Redis health check failed (IGNORE_EXCEPTIONS={ignore_exceptions}): {e}')

    # Optional cache set/get test
    if redis_client:
        try:
            cache.set('health_check_key', 'ok', timeout=5)
            if cache.get('health_check_key') == 'ok':
                redis_details['cache_operation'] = 'ok'
            else:
                redis_details['cache_operation'] = 'degraded'
        except Exception as e:
            redis_details['cache_operation'] = 'failed'
            redis_details['cache_error'] = str(e)

    components['redis'] = {'status': redis_status, 'details': redis_details}

    # ------------------------------------------------------------
    # 3. CELERY (broker + workers)
    # ------------------------------------------------------------
    celery_status = 'ok'
    celery_details = {}
    try:
        conn = celery_app.connection()
        conn.ensure_connection(max_retries=1)
        celery_details['broker'] = {'status': 'ok', 'url': celery_app.conf.broker_url}
        conn.close()

        inspect = celery_app.control.inspect()
        workers = inspect.ping()
        if workers:
            celery_details['workers'] = {
                'count': len(workers),
                'hostnames': list(workers.keys()),
                'status': 'ok',
            }
        else:
            celery_details['workers'] = {'status': 'no_workers', 'note': 'No active workers found.'}
            celery_status = 'degraded'
    except Exception as e:
        celery_status = 'unavailable'
        celery_details['error'] = str(e)
        overall_status = 'degraded'
        logger.warning(f'Celery health check failed: {e}')
    components['celery'] = {'status': celery_status, 'details': celery_details}

    # ------------------------------------------------------------
    # 4. EMAIL BACKEND
    # ------------------------------------------------------------
    email_status = 'ok'
    email_details = {}
    try:
        if 'console' not in settings.EMAIL_BACKEND:
            send_mail(
                subject='Health Check',
                message='Test from health check',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMINS[0][1]],
                fail_silently=False,
            )
            email_details['smtp'] = 'ok'
        else:
            email_details['backend'] = 'console (no test sent)'
    except Exception as e:
        email_status = 'degraded'
        email_details['error'] = str(e)
        overall_status = 'degraded'
    components['email'] = {'status': email_status, 'details': email_details}

    # ------------------------------------------------------------
    # 5. STORAGE (S3) – if configured
    # ------------------------------------------------------------
    storage_status = 'ok'
    storage_details = {}
    if settings.AWS_STORAGE_BUCKET_NAME:
        try:
            import boto3
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )
            s3.head_bucket(Bucket=settings.AWS_STORAGE_BUCKET_NAME)
            storage_details['bucket'] = 'reachable'
        except Exception as e:
            storage_status = 'unavailable'
            storage_details['error'] = str(e)
            overall_status = 'degraded'
    else:
        storage_status = 'skipped'
        storage_details['note'] = 'S3 not configured'
    components['storage'] = {'status': storage_status, 'details': storage_details}

    # ------------------------------------------------------------
    # 6. SYSTEM (disk, python, django, pid) – does NOT degrade overall status
    # ------------------------------------------------------------
    system_details = {}
    try:
        disk = psutil.disk_usage(str(settings.BASE_DIR))
        system_details['disk_usage_percent'] = disk.percent
        system_details['disk_free_gb'] = round(disk.free / (1024 ** 3), 2)
    except Exception as e:
        system_details['disk_error'] = str(e)
        # Not marking overall_status as degraded (original behaviour)
        logger.warning(f"Disk usage check failed: {e}")

    system_details['python_version'] = sys.version.split()[0]
    system_details['django_version'] = getattr(settings, 'DJANGO_VERSION', '4.2+')
    system_details['process_id'] = os.getpid()

    components['system'] = {
        'status': 'ok' if 'disk_error' not in system_details else 'degraded',
        'details': system_details,
    }

    # ------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------
    response_time_ms = round((datetime.now() - start_time).total_seconds() * 1000, 2)

    health_data = {
        'timestamp': datetime.now().isoformat(),
        'status': overall_status,
        'components': components,
        'summary': {
            'response_time_ms': response_time_ms,
            'environment': 'production' if not settings.DEBUG else 'development',
        }
    }
    if request and request.user.is_authenticated:
        health_data['summary']['super_admin'] = request.user.email

    return health_data


# ----------------------------------------------------------------------
# Step 2 – Simplified JSON Endpoint (uses the shared collector)
# ----------------------------------------------------------------------
@require_GET
@never_cache
@staff_member_required
def super_admin_health_check(request):
    """JSON endpoint for monitoring tools (Super Admins only)."""
    if not request.user.is_super_admin:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    health_data = collect_health_data(request)
    status_code = 200 if health_data['status'] == 'ok' else 503
    return JsonResponse(health_data, status=status_code)


# ----------------------------------------------------------------------
# Step 3 – HTML Dashboard View (Super Admins only)
# ✅ FIX: Added aws_bucket_name to context – everything else unchanged
# ----------------------------------------------------------------------
@require_GET
@never_cache
@staff_member_required
def health_dashboard(request):
    """Beautiful HTML dashboard for Super Admins."""
    if not request.user.is_super_admin:
        return render(request, '403.html', status=403)

    health_data = collect_health_data(request)

    # --- Add explicit AWS bucket name for template ---
    aws_bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    if not aws_bucket_name:
        aws_bucket_name = 'Not configured'

    context = {
        'health': health_data,
        'components': health_data['components'],
        'overall_status': health_data['status'],
        'timestamp': health_data['timestamp'],
        'response_time_ms': health_data['summary']['response_time_ms'],
        'environment': health_data['summary']['environment'],
        'super_admin_email': request.user.email,
        'aws_bucket_name': aws_bucket_name,          # ✅ Added
    }
    return render(request, 'health_check/dashboard.html', context)