# FILE: /backend/apps/licenses/management/commands/generate_keys.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from backend.apps.products.models import Software
from backend.apps.accounts.models import User
from ...models import ActivationCode, CodeBatch

class Command(BaseCommand):
    help = 'Generate activation codes for software'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'software_slug',
            type=str,
            help='Slug of the software to generate keys for'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of keys to generate (default: 10)'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['TRIAL', 'STANDARD', 'PREMIUM', 'ENTERPRISE', 'LIFETIME'],
            default='STANDARD',
            help='Type of license keys to generate'
        )
        parser.add_argument(
            '--expires',
            type=int,
            default=365,
            help='Days until expiry (default: 365)'
        )
        parser.add_argument(
            '--max-activations',
            type=int,
            default=1,
            help='Maximum number of activations per key (default: 1)'
        )
        parser.add_argument(
            '--batch-name',
            type=str,
            help='Name for the code batch'
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            help='Email of admin generating the keys'
        )
    
    def handle(self, *args, **options):
        try:
            software = Software.objects.get(slug=options['software_slug'])
        except Software.DoesNotExist:
            raise CommandError(f'Software with slug "{options["software_slug"]}" not found')
        
        admin = None
        if options['admin_email']:
            try:
                admin = User.objects.get(email=options['admin_email'], role__in=['ADMIN', 'SUPER_ADMIN'])
            except User.DoesNotExist:
                raise CommandError(f'Admin user with email "{options["admin_email"]}" not found')
        
        batch = None
        if options['batch_name']:
            batch = CodeBatch.objects.create(
                software=software,
                name=options['batch_name'],
                license_type=options['type'],
                count=options['count'],
                max_activations=options['max_activations'],
                expires_in_days=options['expires'],
                generated_by=admin
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Generating {options["count"]} {options["type"]} keys '
                f'for {software.name} (expires in {options["expires"]} days)'
            )
        )
        
        codes = ActivationCode.generate_for_software(
            software=software,
            count=options['count'],
            license_type=options['type'],
            generated_by=admin,
            expires_in_days=options['expires'],
            max_activations=options['max_activations']
        )
        
        if batch:
            batch.used_count = len(codes)
            batch.is_used = True
            batch.save()
        
        self.stdout.write(self.style.SUCCESS(f'Successfully generated {len(codes)} activation codes:'))
        for i, code in enumerate(codes, 1):
            self.stdout.write(f'{i}. {code.human_code}')
        
        import os
        from django.conf import settings
        
        export_dir = os.path.join(settings.BASE_DIR, 'exports', 'activation_codes')
        os.makedirs(export_dir, exist_ok=True)
        
        filename = os.path.join(
            export_dir,
            f'{software.slug}_{options["type"]}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.txt'
        )
        
        with open(filename, 'w') as f:
            f.write(f'Software: {software.name}\n')
            f.write(f'Type: {options["type"]}\n')
            f.write(f'Generated: {timezone.now().isoformat()}\n')
            f.write(f'Expires: {(timezone.now() + timedelta(days=options["expires"])).isoformat()}\n')
            f.write(f'Max Activations: {options["max_activations"]}\n')
            f.write('\n--- Activation Codes ---\n\n')
            for code in codes:
                f.write(f'{code.human_code}\n')
        
        self.stdout.write(self.style.SUCCESS(f'Codes saved to: {filename}'))