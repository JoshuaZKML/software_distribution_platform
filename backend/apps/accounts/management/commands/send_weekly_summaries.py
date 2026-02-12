# FILE: /backend/apps/accounts/management/commands/send_weekly_summaries.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from backend.apps.accounts.models import User
from backend.apps.accounts.tasks import send_account_summary_email

class Command(BaseCommand):
    help = 'Send weekly account summary emails to all active users'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually sending emails'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Limit number of users to process'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        
        # Get active, verified users who have logged in within last 30 days
        active_threshold = timezone.now() - timedelta(days=30)
        
        users = User.objects.filter(
            is_active=True,
            is_verified=True,
            last_login__gte=active_threshold
        ).order_by('email')
        
        if limit > 0:
            users = users[:limit]
        
        self.stdout.write(f"Found {users.count()} active users to process")
        
        if dry_run:
            self.stdout.write("DRY RUN - No emails will be sent")
            for user in users:
                self.stdout.write(f"  Would send to: {user.email}")
            return
        
        # Send emails
        success_count = 0
        error_count = 0
        
        for user in users:
            try:
                # Send email asynchronously
                send_account_summary_email.delay(str(user.id))
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f"Queued email for: {user.email}"))
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"Failed for {user.email}: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(
            f"Completed: {success_count} queued, {error_count} failed"
        ))