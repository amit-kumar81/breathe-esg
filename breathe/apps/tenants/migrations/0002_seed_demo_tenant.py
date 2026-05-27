from django.db import migrations


def seed_demo_tenant(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    Tenant.objects.get_or_create(name='Demo Company')


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_demo_tenant, migrations.RunPython.noop),
    ]
