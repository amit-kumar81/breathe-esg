"""
Management command: reset_pipeline_data

Deletes all uploaded/processed pipeline data so reviewers start fresh.
Keeps: Tenant, User/UserProfile, DataSource (configuration).
Clears: RawIngestion, ParsedRecord, NormalizedRecord, ReviewTask,
        ReviewApproval, EmissionsDataPoint, AuditLog.

Usage:
    python manage.py reset_pipeline_data
    python manage.py reset_pipeline_data --confirm   (skip prompt)
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Clear all pipeline data (ingestions, records, audit logs). Keeps users and data sources.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            answer = input(
                'This will delete ALL ingestions, parsed/normalized records, '
                'review tasks, and audit logs.\n'
                'Users and DataSources will NOT be affected.\n'
                'Type "yes" to continue: '
            )
            if answer.strip().lower() != 'yes':
                self.stdout.write('Aborted.')
                return

        from django.db import connection

        # Raw SQL bypasses all Django signals and model delete() overrides.
        # Signals fire on ORM deletes and try to write AuditLog rows with
        # tenant_id=None, which violates the NOT NULL constraint outside a
        # request context. Table order respects FK constraints.
        tables = [
            ('audit_audit_log',                  'AuditLog'),
            ('review_review_approval',           'ReviewApproval'),
            ('review_review_task',               'ReviewTask'),
            ('emissions_emissions_data_point',   'EmissionsDataPoint'),
            ('ingest_normalized_record',         'NormalizedRecord'),
            ('ingest_parsed_record',             'ParsedRecord'),
            ('ingest_raw_ingestion',             'RawIngestion'),
        ]

        with connection.cursor() as cursor:
            for table, label in tables:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                count = cursor.fetchone()[0]
                cursor.execute(f'DELETE FROM "{table}"')
                self.stdout.write(f'  {label}: {count} rows deleted')

        self.stdout.write(self.style.SUCCESS('Done. Users and DataSources untouched.'))
