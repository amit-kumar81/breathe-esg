import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_review_status(apps, schema_editor):
    """Copy approved/rejected status from existing ReviewTasks into NormalizedRecord."""
    ReviewTask = apps.get_model('review', 'ReviewTask')
    NormalizedRecord = apps.get_model('ingest', 'NormalizedRecord')

    for task in ReviewTask.objects.filter(status='APPROVED').select_related('normalized_record_id'):
        if task.normalized_record_id_id:
            NormalizedRecord.objects.filter(pk=task.normalized_record_id_id).update(
                review_status='APPROVED',
                reviewed_by_id=task.approved_by_id,
                reviewed_at=task.approved_at,
                reviewer_notes=task.analyst_notes or '',
            )

    for task in ReviewTask.objects.filter(status='REJECTED').select_related('normalized_record_id'):
        if task.normalized_record_id_id:
            NormalizedRecord.objects.filter(pk=task.normalized_record_id_id).update(
                review_status='REJECTED',
                reviewed_by_id=task.rejected_by_id,
                reviewed_at=task.rejected_at,
                reviewer_notes=task.rejection_reason or '',
            )


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0002_seed_datasources'),
        ('review', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='normalizedrecord',
            name='review_status',
            field=models.CharField(
                choices=[
                    ('PENDING_REVIEW', 'Awaiting analyst review'),
                    ('APPROVED', 'Approved for analytics'),
                    ('REJECTED', 'Rejected by analyst'),
                ],
                default='PENDING_REVIEW',
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='normalizedrecord',
            name='reviewed_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviewed_records',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='normalizedrecord',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='normalizedrecord',
            name='reviewer_notes',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='normalizedrecord',
            index=models.Index(fields=['review_status'], name='ingest_norm_review__idx'),
        ),
        migrations.RunPython(backfill_review_status, migrations.RunPython.noop),
    ]
