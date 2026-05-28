"""
Minimal Django Admin for Ingest. No over-engineering.
"""

from django.contrib import admin
from .models import DataSource, RawIngestion, ParsedRecord, NormalizedRecord


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    """Simple read-only admin for data sources."""
    list_display = ('name', 'source_type', 'tenant_id', 'created_at')
    list_filter = ('source_type', 'created_at')
    search_fields = ('name', 'tenant_id__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fields = ('tenant_id', 'source_type', 'name', 'description', 'field_mapping', 'id', 'created_at', 'updated_at')


@admin.register(RawIngestion)
class RawIngestionAdmin(admin.ModelAdmin):
    """
    Simple read-only admin for raw ingestions.

    Design: Pure relational (Option 1)
    - raw_csv_content is the single source of truth
    - Displayed for inspection/debugging only
    - Never modified after creation
    """
    list_display = ('filename', 'data_source_id', 'line_count', 'file_hash', 'created_at')
    list_filter = ('data_source_id__source_type', 'created_at')
    search_fields = ('filename', 'tenant_id__name')
    readonly_fields = ('id', 'file_hash', 'created_at')
    fields = ('tenant_id', 'data_source_id', 'filename', 'file_hash', 'line_count', 'raw_csv_content', 'id', 'created_at')


@admin.register(ParsedRecord)
class ParsedRecordAdmin(admin.ModelAdmin):
    """Simple read-only admin for parsed records."""
    list_display = ('source_row_number', 'ingestion_id', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('ingestion_id__filename', 'tenant_id__name')
    readonly_fields = ('id', 'created_at')
    fields = ('ingestion_id', 'tenant_id', 'source_row_number', 'raw_values', 'parsing_errors', 'id', 'created_at')


@admin.register(NormalizedRecord)
class NormalizedRecordAdmin(admin.ModelAdmin):
    """
    Admin for normalized records.

    - Read-only view of normalized records
    - Shows validation state and quality score
    - Links to parsed records for debugging
    """
    list_display = ('facility_name', 'reporting_year', 'data_quality_score', 'is_valid', 'created_at')
    list_filter = ('is_valid', 'reporting_year', 'created_at')
    search_fields = ('facility_name', 'ingestion_id__filename', 'tenant_id__name')
    readonly_fields = ('id', 'created_at')
    fields = (
        'ingestion_id',
        'parsed_record_id',
        'tenant_id',
        'facility_name',
        'scope_1_emissions',
        'scope_2_emissions',
        'scope_3_emissions',
        'reporting_year',
        'data_quality_score',
        'is_valid',
        'normalized_values',
        'validation_errors',
        'data_quality_flags',
        'id',
        'created_at'
    )
