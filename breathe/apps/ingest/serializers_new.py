"""
Serializers for ingest workflow models.

Chunk 2.1: Django REST Framework Setup & Serializers

Used in /api/ingest/upload/, /api/ingest/{id}/parse/, /api/ingest/{id}/normalize/
"""

from rest_framework import serializers
from breathe.apps.ingest.models import RawIngestion, ParsedRecord, NormalizedRecord


class RawIngestionSerializer(serializers.ModelSerializer):
    """
    Serializer for RawIngestion.
    Shows upload metadata and progress.
    """
    row_count = serializers.IntegerField(read_only=True)
    file_size_bytes = serializers.SerializerMethodField()
    
    class Meta:
        model = RawIngestion
        fields = [
            'id',
            'filename',
            'file_hash',
            'row_count',
            'file_size_bytes',
            'uploaded_at',
            'created_at'
        ]
        read_only_fields = fields
    
    def get_file_size_bytes(self, obj):
        """Return approximate file size in bytes."""
        if obj.raw_content:
            return len(str(obj.raw_content).encode('utf-8'))
        return 0


class ParsedRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for ParsedRecord.
    Shows raw values and parsing errors.
    """
    error_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ParsedRecord
        fields = [
            'id',
            'source_row_number',
            'raw_values',
            'parsing_errors',
            'error_count',
            'created_at'
        ]
        read_only_fields = fields
    
    def get_error_count(self, obj):
        """Count parsing errors."""
        if obj.parsing_errors and isinstance(obj.parsing_errors, list):
            return len(obj.parsing_errors)
        return 0


class NormalizedRecordSimpleSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for NormalizedRecord in list views.
    """
    is_valid = serializers.BooleanField(read_only=True)
    error_count = serializers.SerializerMethodField()
    
    class Meta:
        model = NormalizedRecord
        fields = [
            'id',
            'source_row_number',
            'is_valid',
            'data_quality_score',
            'error_count',
            'created_at'
        ]
        read_only_fields = fields
    
    def get_error_count(self, obj):
        """Count validation errors."""
        if obj.validation_errors and isinstance(obj.validation_errors, list):
            return len(obj.validation_errors)
        return 0


class NormalizedRecordDetailedSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for NormalizedRecord.
    Shows normalized values, validation errors, and quality flags.
    """
    facility_name = serializers.CharField(
        source='normalized_values.facility_name',
        read_only=True,
        allow_null=True
    )
    scope_1_emissions = serializers.FloatField(
        source='normalized_values.scope_1_emissions',
        read_only=True,
        allow_null=True
    )
    scope_2_emissions = serializers.FloatField(
        source='normalized_values.scope_2_emissions',
        read_only=True,
        allow_null=True
    )
    scope_3_emissions = serializers.FloatField(
        source='normalized_values.scope_3_emissions',
        read_only=True,
        allow_null=True
    )
    year = serializers.IntegerField(
        source='normalized_values.year',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = NormalizedRecord
        fields = [
            'id',
            'source_row_number',
            'raw_values',
            'facility_name',
            'scope_1_emissions',
            'scope_2_emissions',
            'scope_3_emissions',
            'year',
            'is_valid',
            'data_quality_score',
            'validation_errors',
            'data_quality_flags',
            'created_at'
        ]
        read_only_fields = fields

