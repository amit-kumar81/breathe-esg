from django.db import migrations


def seed_datasources(apps, schema_editor):
    DataSource = apps.get_model('ingest', 'DataSource')
    Tenant = apps.get_model('tenants', 'Tenant')

    tenant = Tenant.objects.filter(name='Demo Company').first()
    if not tenant:
        return

    DataSource.objects.get_or_create(
        tenant_id=tenant,
        name='Demo SAP Export',
        defaults={
            'source_type': 'SAP',
            'field_mapping': {
                'Plant_Name': 'facility_name',
                'Scope1_MT': 'scope_1_emissions',
                'Scope2_MT': 'scope_2_emissions',
                'Year': 'reporting_year',
            },
            'description': 'Sample SAP CSV export: Plant_Name, Scope1_MT, Scope2_MT, Year',
        }
    )

    DataSource.objects.get_or_create(
        tenant_id=tenant,
        name='SAP GHG Export (mtCO2e)',
        defaults={
            'source_type': 'CSV',
            'field_mapping': {
                'Location': 'facility_name',
                'Scope1_mtCO2e': 'scope_1_emissions',
                'Scope2_mtCO2e': 'scope_2_emissions',
                'Scope3_mtCO2e': 'scope_3_emissions',
                'Fiscal_Year': 'reporting_year',
            },
            'description': 'SAP GHG export: Location, Scope1_mtCO2e, Scope2_mtCO2e, Scope3_mtCO2e, Fiscal_Year',
        }
    )


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0001_initial'),
        ('tenants', '0002_seed_demo_tenant'),
    ]

    operations = [
        migrations.RunPython(seed_datasources, migrations.RunPython.noop),
    ]
