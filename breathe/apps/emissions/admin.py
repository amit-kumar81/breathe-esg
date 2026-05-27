"""
Minimal Django Admin for Emissions. No over-engineering.
"""

from django.contrib import admin
from .models import EmissionsDataPoint


@admin.register(EmissionsDataPoint)
class EmissionsDataPointAdmin(admin.ModelAdmin):
    """Simple read-only admin for emissions data points."""
    list_display = ('facility_name', 'scope', 'emissions_value', 'emissions_unit', 'year', 'is_valid', 'created_at')
    list_filter = ('scope', 'is_valid', 'year', 'created_at')
    search_fields = ('facility_name', 'tenant_id__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fields = (
        'tenant_id', 'parsed_record_id', 'data_source_id',
        'facility_name', 'scope', 'emissions_value', 'emissions_unit', 'year', 'methodology',
        'is_valid', 'normalized_values', 'validation_errors', 'data_quality_flags',
        'id', 'created_at', 'updated_at'
    )
