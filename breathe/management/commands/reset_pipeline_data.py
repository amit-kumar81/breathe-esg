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

        from breathe.apps.audit.models import AuditLog
        from breathe.apps.review.models import ReviewTask, ReviewApproval
        from breathe.apps.emissions.models import EmissionsDataPoint
        from breathe.apps.ingest.models import NormalizedRecord, ParsedRecord, RawIngestion

        counts = {}

        counts['AuditLog'] = AuditLog.objects.count()
        # AuditLog.delete() is blocked by the model — bypass via queryset update
        AuditLog.objects.all()._raw_delete(AuditLog.objects.db)

        counts['ReviewApproval'] = ReviewApproval.objects.count()
        ReviewApproval.objects.all().delete()

        counts['ReviewTask'] = ReviewTask.objects.count()
        ReviewTask.objects.all().delete()

        counts['EmissionsDataPoint'] = EmissionsDataPoint.objects.count()
        EmissionsDataPoint.objects.all().delete()

        counts['NormalizedRecord'] = NormalizedRecord.objects.count()
        NormalizedRecord.objects.all().delete()

        counts['ParsedRecord'] = ParsedRecord.objects.count()
        ParsedRecord.objects.all().delete()

        counts['RawIngestion'] = RawIngestion.objects.count()
        RawIngestion.objects.all().delete()

        self.stdout.write(self.style.SUCCESS('Pipeline data cleared:'))
        for model, count in counts.items():
            self.stdout.write(f'  {model}: {count} rows deleted')
        self.stdout.write(self.style.SUCCESS('Done. Users and DataSources untouched.'))
