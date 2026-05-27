"""
Filter classes for EmissionsDataPoint API endpoints.

Chunk 2.1: Django REST Framework Setup & Serializers

Supports filtering by:
- year (normalized_values.year)
- review_status (PENDING, APPROVED, REJECTED)
- data_source (file name or ID)
- data_quality_score (range)
- facility_name (search)
"""

from django_filters import rest_framework as filters
from breathe.apps.emissions.models import EmissionsDataPoint


class EmissionsDataPointFilter(filters.FilterSet):
    """
    Filter for EmissionsDataPoint list endpoint.
    Supports multiple filter options for analyst dashboard.
    """
    
    # Filter by year (from normalized_values JSONB)
    year = filters.NumberFilter(
        field_name='normalized_values__year',
        lookup_expr='exact',
        label='Reporting Year'
    )
    year_min = filters.NumberFilter(
        field_name='normalized_values__year',
        lookup_expr='gte',
        label='Year (minimum)'
    )
    year_max = filters.NumberFilter(
        field_name='normalized_values__year',
        lookup_expr='lte',
        label='Year (maximum)'
    )
    
    # Filter by review status
    review_status = filters.ChoiceFilter(
        choices=[
            ('PENDING', 'Pending Review'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected'),
        ],
        label='Review Status'
    )
    
    # Filter by data source
    data_source = filters.CharFilter(
        field_name='data_source__source_name',
        lookup_expr='icontains',
        label='Data Source'
    )
    
    # Filter by data quality score (range)
    quality_score_min = filters.NumberFilter(
        field_name='data_quality_score',
        lookup_expr='gte',
        label='Data Quality Score (minimum)'
    )
    quality_score_max = filters.NumberFilter(
        field_name='data_quality_score',
        lookup_expr='lte',
        label='Data Quality Score (maximum)'
    )
    
    # Search by facility name (from normalized_values)
    facility_name = filters.CharFilter(
        field_name='normalized_values__facility_name',
        lookup_expr='icontains',
        label='Facility Name'
    )
    
    # Filter by validation status
    is_valid = filters.BooleanFilter(
        field_name='is_valid',
        label='Valid Records Only'
    )
    
    # Sort by multiple fields
    ordering = filters.OrderingFilter(
        fields=(
            ('created_at', 'Created Date'),
            ('data_quality_score', 'Data Quality'),
            ('normalized_values__year', 'Year'),
        ),
        label='Sort By'
    )
    
    class Meta:
        model = EmissionsDataPoint
        fields = [
            'year',
            'year_min',
            'year_max',
            'review_status',
            'data_source',
            'facility_name',
            'quality_score_min',
            'quality_score_max',
            'is_valid',
            'ordering'
        ]

