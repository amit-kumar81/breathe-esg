from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from breathe.apps.tenants.models import Tenant
from breathe.apps.auth.models import UserProfile
from breathe.apps.ingest.models import DataSource


class Command(BaseCommand):
    help = 'Seed demo data: tenant, analyst user, and a sample data source'

    def handle(self, *args, **options):
        # Demo tenant
        tenant, created = Tenant.objects.get_or_create(
            slug='demo-company',
            defaults={
                'name': 'Demo Company',
                'plan': 'STARTER',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created tenant: {tenant.name}'))
        else:
            self.stdout.write(f'Tenant already exists: {tenant.name}')

        # Demo analyst user
        user, created = User.objects.get_or_create(
            username='analyst@demo.com',
            defaults={
                'email': 'analyst@demo.com',
                'first_name': 'Demo',
                'last_name': 'Analyst',
            }
        )
        if created:
            user.set_password('changeme123')
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created user: {user.username}'))
        else:
            self.stdout.write(f'User already exists: {user.username}')

        # UserProfile linking user to tenant
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'tenant': tenant,
                'role': 'ANALYST',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created profile: {profile}'))
        else:
            self.stdout.write(f'Profile already exists: {profile}')

        # Demo admin user
        admin_user, created = User.objects.get_or_create(
            username='admin@demo.com',
            defaults={
                'email': 'admin@demo.com',
                'first_name': 'Demo',
                'last_name': 'Admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f'Created admin: {admin_user.username}'))
        else:
            self.stdout.write(f'Admin already exists: {admin_user.username}')

        UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={'tenant': tenant, 'role': 'ADMIN', 'is_active': True}
        )

        # Sample data source (needed to test uploads)
        ds, created = DataSource.objects.get_or_create(
            tenant_id=tenant,
            name='Demo SAP Export',
            defaults={
                'source_type': 'SAP',
                'description': 'Sample SAP CSV data source for demo purposes',
                'field_mapping': {
                    'Plant_Name': 'facility_name',
                    'Scope1_MT': 'scope_1_emissions',
                    'Scope2_MT': 'scope_2_emissions',
                    'Year': 'reporting_year',
                }
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created data source: {ds.name}'))
        else:
            self.stdout.write(f'Data source already exists: {ds.name}')

        self.stdout.write(self.style.SUCCESS('\nSeed complete.'))
        self.stdout.write('  Login: analyst@demo.com / changeme123')
        self.stdout.write('  Admin: admin@demo.com / admin123')
        self.stdout.write('  Tenant: Demo Company (demo-company)')
