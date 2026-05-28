from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from breathe.apps.tenants.models import Tenant
from breathe.apps.auth.models import UserProfile
from breathe.apps.ingest.models import DataSource


class Command(BaseCommand):
    help = 'Seed demo data: tenant, users, and one DataSource per source type'

    def handle(self, *args, **options):
        # --- Tenant ---
        tenant, created = Tenant.objects.get_or_create(
            slug='demo-company',
            defaults={'name': 'Demo Company', 'plan': 'STARTER', 'is_active': True},
        )
        self.stdout.write(f'{"Created" if created else "Exists"}: tenant {tenant.name}')

        # --- Users ---
        analyst, created = User.objects.get_or_create(
            username='analyst@demo.com',
            defaults={'email': 'analyst@demo.com', 'first_name': 'Demo', 'last_name': 'Analyst'},
        )
        if created:
            analyst.set_password('changeme123')
            analyst.save()
        UserProfile.objects.get_or_create(
            user=analyst,
            defaults={'tenant': tenant, 'role': 'ANALYST', 'is_active': True},
        )
        self.stdout.write(f'{"Created" if created else "Exists"}: analyst@demo.com')

        admin_user, created = User.objects.get_or_create(
            username='admin@demo.com',
            defaults={
                'email': 'admin@demo.com', 'first_name': 'Demo', 'last_name': 'Admin',
                'is_staff': True, 'is_superuser': True,
            },
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
        UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={'tenant': tenant, 'role': 'ADMIN', 'is_active': True},
        )
        self.stdout.write(f'{"Created" if created else "Exists"}: admin@demo.com')

        # --- Data Sources (one per source type) ---
        # Each field_mapping maps the actual CSV column header to our internal standard field name.
        # These match the sample files in sap_samples/, utility_samples/, travel_samples/.

        sources = [
            {
                'name': 'SAP GHG Export (Semicolon CSV)',
                'source_type': 'SAP',
                'description': (
                    'Flat-file export from SAP Environmental Compliance module via SE16N. '
                    'Semicolon-delimited, German column names, dates in DD.MM.YYYY, '
                    'values already in tCO2e (metric tons CO2 equivalent).'
                ),
                'field_mapping': {
                    'Werksname':     'facility_name',
                    'Buchungsjahr':  'reporting_year',
                    'Scope1_tCO2e':  'scope_1_emissions',
                    'Scope2_tCO2e':  'scope_2_emissions',
                    'Scope3_tCO2e':  'scope_3_emissions',
                },
            },
            {
                'name': 'Utility Portal CSV (MSEDCL/Adani format)',
                'source_type': 'UTILITY',
                'description': (
                    'CSV export from electricity utility web portal (MSEDCL/Adani Electricity Mumbai). '
                    'Billing periods do not align with calendar months. '
                    'Raw kWh usage; emission factor applied during normalization '
                    '(CEA India 2022-23 baseline: 0.716 kgCO2e/kWh → Scope 2).'
                ),
                'field_mapping': {
                    'Site_Name':     'facility_name',
                    'Billing_Start': 'billing_period_start',
                    'Billing_End':   'billing_period_end',
                    'Usage_kWh':     'usage_kwh',
                },
            },
            {
                'name': 'Concur Travel Expense Export',
                'source_type': 'TRAVEL',
                'description': (
                    'CSV export from SAP Concur expense management system. '
                    'One row per expense line item (flight segment, hotel night, or ground transport). '
                    'CO2e calculated per row using ICAO 2023 (flights) and DEFRA 2023 (hotels, cars). '
                    'All travel is Scope 3 Category 6: Business Travel.'
                ),
                'field_mapping': {
                    'Employee_ID':       'employee_id',
                    'Transaction_Date':  'transaction_date',
                    'Expense_Type':      'expense_type',
                    'Origin_IATA':       'origin_iata',
                    'Destination_IATA':  'destination_iata',
                    'Distance_km':       'distance_km',
                    'Hotel_Nights':      'hotel_nights',
                    'Business_Purpose':  'business_purpose',
                },
            },
        ]

        for sd in sources:
            ds, created = DataSource.objects.get_or_create(
                tenant_id=tenant,
                name=sd['name'],
                defaults={
                    'source_type': sd['source_type'],
                    'description': sd['description'],
                    'field_mapping': sd['field_mapping'],
                },
            )
            self.stdout.write(f'{"Created" if created else "Exists"}: DataSource "{ds.name}"')

        self.stdout.write(self.style.SUCCESS('\nSeed complete.'))
        self.stdout.write('  analyst@demo.com / changeme123')
        self.stdout.write('  admin@demo.com   / admin123')
