"""
Filter classes for EmissionsDataPoint API endpoints.
"""

from django_filters import rest_framework as filters
from breathe.apps.emissions.models import EmissionsDataPoint


class EmissionsDataPointFilter(filters.FilterSet):
    year = filters.NumberFilter(field_name='year', lookup_expr='exact')
    year_min = filters.NumberFilter(field_name='year', lookup_expr='gte')
    year_max = filters.NumberFilter(field_name='year', lookup_expr='lte')
    scope = filters.ChoiceFilter(choices=EmissionsDataPoint.SCOPE_CHOICES)
    facility_name = filters.CharFilter(field_name='facility_name', lookup_expr='icontains')
    is_valid = filters.BooleanFilter(field_name='is_valid')

    class Meta:
        model = EmissionsDataPoint
        fields = ['year', 'year_min', 'year_max', 'scope', 'facility_name', 'is_valid']
