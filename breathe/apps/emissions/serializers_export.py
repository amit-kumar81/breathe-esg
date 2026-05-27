"""
Chunk 2.5: Data Export & Reporting - Serializers

Serializers for export and reporting endpoints.
"""

from rest_framework import serializers
from .models import EmissionsDataPoint


class EmissionsExportSerializer(serializers.ModelSerializer):
    """
    Serializer for CSV/JSON export.

    Flattens emissions data for export, includes audit context.
    """
    analyst_name = serializers.SerializerMethodField()
    facility_name = serializers.CharField(
        source='normalized_record.normalized_values.facility_name',
        read_only=True
    )
    scope_1_emissions = serializers.DecimalField(
        source='normalized_record.normalized_values.scope_1_emissions',
        max_digits=15,
        decimal_places=4,
        read_only=True
    )
    scope_2_emissions = serializers.DecimalField(
        source='normalized_record.normalized_values.scope_2_emissions',
        max_digits=15,
        decimal_places=4,
        read_only=True
    )
    scope_3_emissions = serializers.DecimalField(
        source='normalized_record.normalized_values.scope_3_emissions',
        max_digits=15,
        decimal_places=4,
        read_only=True
    )
    reporting_year = serializers.IntegerField(
        source='normalized_record.normalized_values.reporting_year',
        read_only=True
    )

    class Meta:
        model = EmissionsDataPoint
        fields = [
            'id',
            'facility_name',
            'scope_1_emissions',
            'scope_2_emissions',
            'scope_3_emissions',
            'reporting_year',
            'review_status',
            'data_quality_score',
            'analyst_name',
            'created_at'
        ]

    def get_analyst_name(self, obj):
        """Get analyst who approved this record"""
        try:
            # Get the latest approval
            from breathe.apps.review.models import ReviewApproval
            approval = ReviewApproval.objects.filter(
                review_task__normalized_record=obj.normalized_record
            ).order_by('-created_at').first()

            if approval:
                return approval.analyst.username
            return None
        except Exception:
            return None


class ReportingSummarySerializer(serializers.Serializer):
    """
    Serializer for reporting summary statistics.

    Used for dashboard endpoints.
    """
    total_records = serializers.IntegerField()
    approved_records = serializers.IntegerField()
    pending_records = serializers.IntegerField()
    rejected_records = serializers.IntegerField()
    auto_approved_records = serializers.IntegerField()

    by_status = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Count of records by review status"
    )
    by_year = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Count of records by reporting year"
    )
    by_facility = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Count of records by facility"
    )
    by_quality_tier = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Count of records by quality score tier"
    )

    average_quality_score = serializers.FloatField()
    average_scope_1 = serializers.FloatField()
    average_scope_2 = serializers.FloatField()
    average_scope_3 = serializers.FloatField()

    total_scope_1 = serializers.FloatField(help_text="Sum of all Scope 1 emissions")
    total_scope_2 = serializers.FloatField(help_text="Sum of all Scope 2 emissions")
    total_scope_3 = serializers.FloatField(help_text="Sum of all Scope 3 emissions")
    total_emissions = serializers.FloatField(help_text="Sum of all scopes")


class ExportMetadataSerializer(serializers.Serializer):
    """
    Serializer for export metadata.

    Included in JSON exports as context.
    """
    export_timestamp = serializers.DateTimeField()
    export_format = serializers.CharField()
    tenant_name = serializers.CharField()
    record_count = serializers.IntegerField()
    filters_applied = serializers.DictField(required=False)
    generated_by = serializers.CharField(help_text="Username of user who exported")
