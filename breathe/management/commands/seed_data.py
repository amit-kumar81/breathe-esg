"""
Management command to seed initial data for development/testing.

Usage:
  python manage.py seed_data
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from breathe.apps.tenants.models import Tenant
from breathe.apps.auth.models import UserProfile


class Command(BaseCommand):
    help = 'Seed database with demo tenant and user for development'

    def handle(self, *args, **options):
        self.stdout.write('Starting data seed...')

        # Create demo tenant
        tenant, created = Tenant.objects.get_or_create(
            slug='demo',
            defaults={
                'name': 'Demo Company',
                'description': 'Demo tenant for testing'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created tenant: {tenant.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'✓ Tenant already exists: {tenant.name}'))

        # Create demo analyst user
        user, created = User.objects.get_or_create(
            username='analyst@demo.com',
            defaults={
                'email': 'analyst@demo.com',
                'first_name': 'Demo',
                'last_name': 'Analyst',
                'is_staff': True,
                'is_active': True
            }
        )
        if created:
            # Set a default password (should be changed in practice)
            user.set_password('demo123456')
            user.save()
            self.stdout.write(self.style.SUCCESS(f'✓ Created user: {user.email}'))
            self.stdout.write(self.style.WARNING('  Note: Default password is "demo123456" - change immediately!'))
        else:
            self.stdout.write(self.style.WARNING(f'✓ User already exists: {user.email}'))

        # Create user profile linking user to tenant
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'tenant': tenant,
                'role': 'ANALYST'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created user profile: {user.email} -> {tenant.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'✓ User profile already exists'))

        # Create data provider user (optional)
        provider_user, created = User.objects.get_or_create(
            username='provider@demo.com',
            defaults={
                'email': 'provider@demo.com',
                'first_name': 'Demo',
                'last_name': 'Provider',
                'is_staff': False,
                'is_active': True
            }
        )
        if created:
            provider_user.set_password('demo123456')
            provider_user.save()
            self.stdout.write(self.style.SUCCESS(f'✓ Created user: {provider_user.email}'))
        else:
            self.stdout.write(self.style.WARNING(f'✓ User already exists: {provider_user.email}'))

        # Create profile for provider
        provider_profile, created = UserProfile.objects.get_or_create(
            user=provider_user,
            defaults={
                'tenant': tenant,
                'role': 'PROVIDER'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created provider profile'))
        else:
            self.stdout.write(self.style.WARNING(f'✓ Provider profile already exists'))

        self.stdout.write(self.style.SUCCESS('✓ Data seed complete!'))
        self.stdout.write('')
        self.stdout.write('Demo Credentials:')
        self.stdout.write(f'  Analyst Email: analyst@demo.com')
        self.stdout.write(f'  Analyst Password: demo123456')
        self.stdout.write(f'  Provider Email: provider@demo.com')
        self.stdout.write(f'  Provider Password: demo123456')
        self.stdout.write(f'  Tenant: {tenant.name}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('⚠️  Change these credentials immediately in production!'))
