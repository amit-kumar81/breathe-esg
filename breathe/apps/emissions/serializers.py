"""
Serializers for EmissionsDataPoint, NormalizedRecord, and related models.

Chunk 2.1: Django REST Framework Setup & Serializers

Design Philosophy:
- Flatten nested JSON (normalized_values) for easier frontend consumption
- Include related data (audit trail, validation errors) for full context
- Gracefully handle missing/invalid fields
- Separate list vs. detail serializers for performance
"""

from rest_framework import serializers
from breathe.apps.emissions.models import EmissionsDataPoint
from breathe.apps.ingest.models import NormalizedRecord
from breathe.apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializes AuditLog for inclusion in audit trail endpoints.
    """
    user_name = serializers.CharField(source='user_id.username', read_only=True, allow_null=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'action',
            'timestamp',
            'user_name',
            'ip_address',
            'change_summary'
        ]
        read_only_fields = fields


class EmissionsDataPointListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing EmissionsDataPoints.
    Flattens normalized_values for easier frontend consumption.
    Excludes heavy fields like full validation errors.
    """
    # Flatten normalized_values (core ESG fields)
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
    methodology = serializers.CharField(
        source='normalized_values.methodology',
        read_only=True,
        allow_null=True
    )
    
    # Count of validation issues
    validation_error_count = serializers.SerializerMethodField()
    data_quality_flag_count = serializers.SerializerMethodField()
    
    class Meta:
        model = EmissionsDataPoint
        fields = [
            'id',
            'facility_name',
            'scope_1_emissions',
            'scope_2_emissions',
            'scope_3_emissions',
            'year',
            'methodology',
            'review_status',
            'data_quality_score',
            'validation_error_count',
            'data_quality_flag_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = fields
    
    def get_validation_error_count(self, obj):
        """Count validation errors from validation_errors JSONB."""
        if obj.validation_errors and isinstance(obj.validation_errors, list):
            return len(obj.validation_errors)
        return 0
    
    def get_data_quality_flag_count(self, obj):
        """Count data quality flags from data_quality_flags JSONB."""
        if obj.data_quality_flags and isinstance(obj.data_quality_flags, list):
            return len(obj.data_quality_flags)
        return 0


class EmissionsDataPointDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for EmissionsDataPoint.
    Includes all fields: normalized values, validation errors, audit trail.
    Used for GET /api/emissions/{id}/ endpoint.
    """
    # Flatten normalized_values (core ESG fields)
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
    methodology = serializers.CharField(
        source='normalized_values.methodology',
        read_only=True,
        allow_null=True
    )
    data_quality_flag = serializers.CharField(
        source='normalized_values.data_quality_flag',
        read_only=True,
        allow_null=True
    )
    
    # Include validation errors and flags (full detail)
    validation_errors = serializers.JSONField(read_only=True)
    data_quality_flags = serializers.JSONField(read_only=True)
    
    # Metadata
    data_source_name = serializers.CharField(
        source='data_source.source_name',
        read_only=True,
        allow_null=True
    )
    
    # Recent audit trail (last 5 changes)
    recent_changes = serializers.SerializerMethodField()
    
    class Meta:
        model = EmissionsDataPoint
        fields = [
            'id',
            'facility_name',
            'scope_1_emissions',
            'scope_2_emissions',
            'scope_3_emissions',
            'year',
            'methodology',
            'data_quality_flag',
            'validation_errors',
            'data_quality_flags',
            'data_quality_score',
            'review_status',
            'data_source_name',
            'reviewed_at',
            'reviewer_notes',
            'created_at',
            'updated_at',
            'recent_changes'
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'recent_changes'
        ]
    
    def get_recent_changes(self, obj):
        """Retrieve last 5 audit log entries for this object."""
        audits = AuditLog.objects.filter(
            object_type='EmissionsDataPoint',
            object_id=str(obj.id)
        ).order_by('-timestamp')[:5]
        
        return AuditLogSerializer(audits, many=True).data


class NormalizedRecordListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing NormalizedRecords.
    Used in ingest workflow to show parsing/normalization results.
    """
    # Show validation status
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


class NormalizedRecordDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for NormalizedRecord.
    Shows normalized values and validation details.
    """
    # Show normalized fields
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
            'year',
            'is_valid',
            'data_quality_score',
            'validation_errors',
            'data_quality_flags',
            'created_at'
        ]
        read_only_fields = fields

