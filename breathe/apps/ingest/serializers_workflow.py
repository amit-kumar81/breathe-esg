"""
Chunk 2.4: Ingestion Workflow Endpoints - Serializers

Serializers for the ingestion workflow:
- IngestionUploadSerializer: Accept CSV file upload
- IngestionStatusSerializer: Return progress summary
- IngestionDetailSerializer: Complete ingestion details
"""

from rest_framework import serializers
from .models import RawIngestion, ParsedRecord, NormalizedRecord
from breathe.apps.emissions.models import DataSource


class IngestionStatusSummarySerializer(serializers.Serializer):
    """
    Summary statistics for an ingestion.

    Used in the status endpoint to show progress.
    """
    total_rows = serializers.IntegerField(help_text="Total rows in CSV")
    parsed_rows = serializers.IntegerField(help_text="Successfully parsed")
    valid_rows = serializers.IntegerField(help_text="Passed validation")
    rows_with_warnings = serializers.IntegerField(help_text="Has data quality flags")
    rows_with_errors = serializers.IntegerField(help_text="Failed validation")
    error_rows = serializers.SerializerMethodField(help_text="Total errors + warnings")
    success_rate = serializers.SerializerMethodField(help_text="Percentage of valid rows")

    def get_error_rows(self, obj):
        return obj.rows_with_errors + obj.rows_with_warnings

    def get_success_rate(self, obj):
        if obj.parsed_rows == 0:
            return 0
        return round((obj.valid_rows / obj.parsed_rows) * 100, 2)


class IngestionUploadSerializer(serializers.Serializer):
    """
    Input for POST /api/ingest/upload/.

    Accepts:
    - data_source_id: Which data source this file belongs to
    - file: CSV file to upload
    """
    data_source_id = serializers.UUIDField()
    file = serializers.FileField(help_text="CSV file to upload")

    def validate_file(self, file):
        """Validate file is reasonable size"""
        max_size = 50 * 1024 * 1024  # 50 MB
        if file.size > max_size:
            raise serializers.ValidationError(f"File size exceeds {max_size} bytes")
        return file

    def validate_data_source_id(self, data_source_id):
        """Verify data source exists"""
        from breathe.apps.emissions.models import DataSource
        if not DataSource.objects.filter(id=data_source_id).exists():
            raise serializers.ValidationError("DataSource not found")
        return data_source_id


class ParsedRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for a single parsed row.
    """
    class Meta:
        model = ParsedRecord
        fields = ['source_row_number', 'raw_values', 'parsing_errors']


class NormalizedRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for a normalized record.
    """
    class Meta:
        model = NormalizedRecord
        fields = [
            'id',
            'facility_name',
            'scope_1_emissions',
            'scope_2_emissions',
            'scope_3_emissions',
            'reporting_year',
            'is_valid',
            'data_quality_score',
            'normalized_values',
            'validation_errors',
            'data_quality_flags'
        ]


class IngestionStatusSerializer(serializers.ModelSerializer):
    """
    Response for GET /api/ingest/{id}/status/.

    Returns:
    - Ingestion metadata
    - Current status
    - Progress summary
    - Steps completed
    """
    summary = IngestionStatusSummarySerializer(source='*', read_only=True)
    steps_completed = serializers.SerializerMethodField()
    completed_percentage = serializers.SerializerMethodField()

    class Meta:
        model = RawIngestion
        fields = [
            'id',
            'filename',
            'status',
            'steps_completed',
            'completed_percentage',
            'summary',
            'dialect_detected',
            'created_at',
            'uploaded_at',
            'parsed_at',
            'normalized_at',
            'completed_at',
            'error_message'
        ]

    def get_steps_completed(self, obj):
        """Return list of completed steps"""
        steps = []
        if obj.uploaded_at:
            steps.append('upload')
        if obj.parsed_at:
            steps.append('parse')
        if obj.normalized_at:
            steps.append('normalize')
        if obj.status == 'COMPLETE':
            steps.append('complete')
        return steps

    def get_completed_percentage(self, obj):
        """Return completion percentage"""
        return obj.completed_percentage


class IngestionDetailSerializer(serializers.ModelSerializer):
    """
    Response for GET /api/ingest/{id}/.

    Detailed view including:
    - File info
    - Processing status
    - Row counts
    - Sample parsed records
    - Sample normalized records
    """
    summary = IngestionStatusSummarySerializer(source='*', read_only=True)
    steps_completed = serializers.SerializerMethodField()
    sample_parsed_records = serializers.SerializerMethodField()
    sample_normalized_records = serializers.SerializerMethodField()

    class Meta:
        model = RawIngestion
        fields = [
            'id',
            'filename',
            'file_size',
            'status',
            'steps_completed',
            'summary',
            'dialect_detected',
            'field_mapping_used',
            'sample_parsed_records',
            'sample_normalized_records',
            'created_at',
            'uploaded_at',
            'parsed_at',
            'normalized_at',
            'completed_at',
            'error_message'
        ]

    def get_steps_completed(self, obj):
        """Return list of completed steps"""
        steps = []
        if obj.uploaded_at:
            steps.append('upload')
        if obj.parsed_at:
            steps.append('parse')
        if obj.normalized_at:
            steps.append('normalize')
        return steps

    def get_sample_parsed_records(self, obj):
        """Return first 5 parsed records (with errors highlighted)"""
        records = ParsedRecord.objects.filter(
            ingestion_id=obj.id,
            parsing_errors__isnull=False
        )[:5]
        return ParsedRecordSerializer(records, many=True).data

    def get_sample_normalized_records(self, obj):
        """Return first 5 normalized records (with validation errors)"""
        records = NormalizedRecord.objects.filter(
            ingestion_id=obj.id,
            is_valid=False
        )[:5]
        return NormalizedRecordSerializer(records, many=True).data


class IngestionListSerializer(serializers.ModelSerializer):
    """
    Response for GET /api/ingest/ (list).

    Lightweight view for list endpoint.
    """
    summary = IngestionStatusSummarySerializer(source='*', read_only=True)

    class Meta:
        model = RawIngestion
        fields = [
            'id',
            'filename',
            'status',
            'summary',
            'created_at',
            'completed_at'
        ]
