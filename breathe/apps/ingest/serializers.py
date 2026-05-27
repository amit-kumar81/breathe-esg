"""
DRF Serializers for ingest endpoints.

Design:
- Flat, simple serializers (no nested relations for MVP)
- Use ListField to accept raw CSV rows
- Validate at serializer level (file format, size, etc.)
"""

import csv
import io
from rest_framework import serializers
from .models import DataSource, RawIngestion


class DataSourceSerializer(serializers.ModelSerializer):
    """Serializer for DataSource metadata."""

    class Meta:
        model = DataSource
        fields = ['id', 'source_type', 'name', 'description', 'field_mapping', 'created_at']
        read_only_fields = ['id', 'created_at']


class IngestionUploadSerializer(serializers.Serializer):
    """
    Serializer for CSV file upload.

    Accepts multipart/form-data:
    - file: CSV file (required)
    - data_source_id: UUID of the data source (required)
    - description: Optional metadata (optional)

    Returns:
    - ingestion_id: UUID of created RawIngestion
    - status: 'received' (always on success)
    - line_count: Number of rows in file
    - filename: Original filename
    """
    file = serializers.FileField(required=True, help_text="CSV file to upload (max 10MB)")
    data_source_id = serializers.UUIDField(required=True, help_text="ID of the DataSource this file is from")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Optional notes about this upload")

    def validate_file(self, value):
        """Validate file is CSV and under size limit."""
        # Check MIME type
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError("File must be a CSV (.csv)")

        # Check file size (10MB max for MVP)
        if value.size > 10 * 1024 * 1024:  # 10MB
            raise serializers.ValidationError("File size exceeds 10MB limit")

        return value

    def validate(self, data):
        """
        Validate that:
        1. DataSource exists and belongs to the user's tenant
        2. CSV file is readable and has valid structure
        """
        file_obj = data.get('file')
        data_source_id = data.get('data_source_id')
        request = self.context.get('request')

        # Get DataSource
        try:
            data_source = DataSource.objects.get(id=data_source_id)
        except DataSource.DoesNotExist:
            raise serializers.ValidationError("DataSource not found")

        # Tenant isolation: user's tenant must match data source's tenant
        # Note: In Chunk 2.3, we'll add actual user auth. For now, this is a placeholder.
        if not hasattr(request, 'tenant_id'):
            # For now, allow all. This will be fixed in Chunk 2.3 (auth)
            pass
        else:
            if str(data_source.tenant_id) != str(request.tenant_id):
                raise serializers.ValidationError("DataSource does not belong to your tenant")

        # Try to parse CSV to validate structure
        try:
            file_obj.seek(0)
            text_content = file_obj.read().decode('utf-8')
            file_obj.seek(0)  # Reset for the view to read later

            reader = csv.DictReader(io.StringIO(text_content))
            rows = list(reader)

            if not rows:
                raise serializers.ValidationError("CSV file is empty")

            data['_parsed_rows'] = rows
            data['_field_names'] = list(rows[0].keys()) if rows else []

        except UnicodeDecodeError:
            raise serializers.ValidationError("File must be UTF-8 encoded")
        except csv.Error as e:
            raise serializers.ValidationError(f"Invalid CSV format: {str(e)}")

        data['_data_source'] = data_source
        return data

    def create(self, validated_data):
        """
        Create RawIngestion record.

        This is NOT called during standard serializer.save() in views.
        We use it in the view to handle the creation with proper tenant isolation.
        """
        raise NotImplementedError("Use view to create RawIngestion")


class RawIngestionListSerializer(serializers.ModelSerializer):
    """Serializer for listing RawIngestion records."""
    data_source_name = serializers.CharField(source='data_source_id.name', read_only=True)

    class Meta:
        model = RawIngestion
        fields = ['id', 'filename', 'data_source_name', 'line_count', 'file_hash', 'created_at']
        read_only_fields = ['id', 'file_hash', 'created_at']


class RawIngestionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for RawIngestion detail view (includes original CSV content).

    Design: Pure Relational (Option 1)
    - raw_csv_content: Original CSV file as text (single source of truth)
    - Parsing happens on-demand in Chunk 1.3 (no data loss risk)
    """
    data_source = DataSourceSerializer(source='data_source_id', read_only=True)

    class Meta:
        model = RawIngestion
        fields = ['id', 'filename', 'file_hash', 'line_count', 'raw_csv_content', 'data_source', 'created_at']
        read_only_fields = ['id', 'file_hash', 'created_at']


class ParseRequestSerializer(serializers.Serializer):
    """
    Serializer for parse request.

    No input validation needed—the ingestion_id is in the URL.
    Returns parsing summary on success.
    """
    class Meta:
        fields = []  # No input fields


class ParseResponseSerializer(serializers.Serializer):
    """
    Serializer for parse response.

    Returns summary of parsing operation.
    """
    ingestion_id = serializers.UUIDField(help_text="ID of the RawIngestion")
    status = serializers.CharField(help_text="'parsed' or 'already_parsed'")
    total_rows = serializers.IntegerField(help_text="Total rows in file")
    parsed_records_created = serializers.IntegerField(help_text="ParsedRecords created in this operation")
    parsing_errors = serializers.ListField(child=serializers.CharField())
    message = serializers.CharField()


class ParsedRecordListSerializer(serializers.ModelSerializer):
    """Serializer for listing ParsedRecords."""
    ingestion_filename = serializers.CharField(source='ingestion_id.filename', read_only=True)

    class Meta:
        from .models import ParsedRecord
        model = ParsedRecord
        fields = ['id', 'source_row_number', 'ingestion_filename', 'parsing_errors', 'created_at']
        read_only_fields = ['id', 'created_at']


class ParsedRecordDetailSerializer(serializers.ModelSerializer):
    """Serializer for ParsedRecord detail view (includes raw values)."""
    ingestion = RawIngestionDetailSerializer(source='ingestion_id', read_only=True)

    class Meta:
        from .models import ParsedRecord
        model = ParsedRecord
        fields = ['id', 'source_row_number', 'raw_values', 'parsing_errors', 'ingestion', 'created_at']
        read_only_fields = ['id', 'created_at']


class NormalizationRequestSerializer(serializers.Serializer):
    """
    Serializer for normalization request.

    No input needed—ingestion_id is in URL.
    """
    class Meta:
        fields = []


class NormalizationResponseSerializer(serializers.Serializer):
    """
    Serializer for normalization response.

    Returns summary of normalization operation.
    """
    ingestion_id = serializers.UUIDField(help_text="ID of the RawIngestion")
    status = serializers.CharField(help_text="'normalized'")
    total_parsed_records = serializers.IntegerField(help_text="Total ParsedRecords from this ingestion")
    total_normalized_records = serializers.IntegerField(help_text="NormalizedRecords created")
    valid_records_count = serializers.IntegerField(help_text="Records with no validation errors")
    invalid_records_count = serializers.IntegerField(help_text="Records with validation errors")
    normalization_errors = serializers.ListField(child=serializers.DictField())
    message = serializers.CharField()


class NormalizedRecordListSerializer(serializers.ModelSerializer):
    """Serializer for listing NormalizedRecords."""
    ingestion_filename = serializers.CharField(source='ingestion_id.filename', read_only=True)

    class Meta:
        from .models import NormalizedRecord
        model = NormalizedRecord
        fields = [
            'id', 'facility_name', 'scope_1_emissions', 'reporting_year',
            'is_valid', 'data_quality_score', 'ingestion_filename', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class NormalizedRecordDetailSerializer(serializers.ModelSerializer):
    """Serializer for NormalizedRecord detail view (includes all validation info)."""
    parsed_record = ParsedRecordDetailSerializer(source='parsed_record_id', read_only=True)

    class Meta:
        from .models import NormalizedRecord
        model = NormalizedRecord
        fields = [
            'id', 'facility_name', 'scope_1_emissions', 'scope_2_emissions',
            'scope_3_emissions', 'reporting_year', 'data_quality_score',
            'normalized_values', 'validation_errors', 'data_quality_flags',
            'is_valid', 'parsed_record', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
