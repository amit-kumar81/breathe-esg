"""
Analytics views — read approved NormalizedRecords directly.

No intermediate EmissionsDataPoint table. The pipeline is:
    RawIngestion → ParsedRecord → NormalizedRecord (review_status=APPROVED) → here

GET /api/emissions/summary/  dashboard metrics + chart data
GET /api/emissions/          paginated approved records
GET /api/emissions/{id}/     record detail
"""

from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Avg, Count, Q, Coalesce, Value

from breathe.apps.ingest.models import NormalizedRecord


def _approved():
    return NormalizedRecord.objects.filter(review_status='APPROVED')


class EmissionsDataPointViewSet(viewsets.ViewSet):
    """
    Read-only analytics over approved NormalizedRecords.
    URL prefix: /api/emissions/
    """

    def list(self, request):
        """GET /api/emissions/ — paginated approved records."""
        from rest_framework.pagination import PageNumberPagination

        qs = _approved().select_related('reviewed_by')

        facility = request.query_params.get('facility_name')
        year = request.query_params.get('year')
        if facility:
            qs = qs.filter(facility_name__icontains=facility)
        if year:
            qs = qs.filter(reporting_year=int(year))

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(qs, request)

        def serialize(nr):
            return {
                'id': str(nr.id),
                'facility_name': nr.facility_name,
                'reporting_year': nr.reporting_year,
                'scope_1_emissions': float(nr.scope_1_emissions) if nr.scope_1_emissions is not None else None,
                'scope_2_emissions': float(nr.scope_2_emissions) if nr.scope_2_emissions is not None else None,
                'scope_3_emissions': float(nr.scope_3_emissions) if nr.scope_3_emissions is not None else None,
                'data_quality_score': nr.data_quality_score,
                'is_valid': nr.is_valid,
                'reviewed_at': nr.reviewed_at,
            }

        if page is not None:
            return paginator.get_paginated_response([serialize(nr) for nr in page])
        return Response({'count': qs.count(), 'results': [serialize(nr) for nr in qs]})

    def retrieve(self, request, pk=None):
        """GET /api/emissions/{id}/"""
        try:
            nr = _approved().get(id=pk)
        except NormalizedRecord.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'id': str(nr.id),
            'facility_name': nr.facility_name,
            'reporting_year': nr.reporting_year,
            'scope_1_emissions': float(nr.scope_1_emissions) if nr.scope_1_emissions is not None else None,
            'scope_2_emissions': float(nr.scope_2_emissions) if nr.scope_2_emissions is not None else None,
            'scope_3_emissions': float(nr.scope_3_emissions) if nr.scope_3_emissions is not None else None,
            'data_quality_score': nr.data_quality_score,
            'validation_errors': nr.validation_errors,
            'normalized_values': nr.normalized_values,
            'is_valid': nr.is_valid,
            'reviewed_at': nr.reviewed_at,
        })

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        GET /api/emissions/summary/
        Optional: ?year=2023  ?facility_name=Bangalore  ?scope=SCOPE_1

        Returns aggregated metrics for the dashboard:
        - total_emissions, record_count, facility_count, average_quality_score
        - available_years, available_facilities  (always unfiltered, for dropdowns)
        - by_scope  [{scope, value}]  bar chart
        - by_year   [{year, scope_1, scope_2, scope_3}]  line chart
        """
        all_qs = _approved()

        # Dropdown options always show everything (unfiltered)
        available_years = list(
            all_qs.order_by('reporting_year')
            .values_list('reporting_year', flat=True)
            .distinct()
        )
        available_facilities = sorted(
            all_qs.values_list('facility_name', flat=True).distinct()
        )

        # Apply filters to the metrics queryset
        qs = all_qs
        year = request.query_params.get('year')
        facility_name = request.query_params.get('facility_name')
        scope = request.query_params.get('scope', '').upper()

        if year:
            qs = qs.filter(reporting_year=int(year))
        if facility_name:
            qs = qs.filter(facility_name=facility_name)

        # Scope filter: restrict which emission columns are included
        ZERO = Value(Decimal('0'))
        if scope == 'SCOPE_1':
            s1 = float(qs.aggregate(t=Coalesce(Sum('scope_1_emissions'), ZERO))['t'])
            s2, s3 = 0.0, 0.0
        elif scope == 'SCOPE_2':
            s2 = float(qs.aggregate(t=Coalesce(Sum('scope_2_emissions'), ZERO))['t'])
            s1, s3 = 0.0, 0.0
        elif scope == 'SCOPE_3':
            s3 = float(qs.aggregate(t=Coalesce(Sum('scope_3_emissions'), ZERO))['t'])
            s1, s2 = 0.0, 0.0
        else:
            agg = qs.aggregate(
                s1=Coalesce(Sum('scope_1_emissions'), ZERO),
                s2=Coalesce(Sum('scope_2_emissions'), ZERO),
                s3=Coalesce(Sum('scope_3_emissions'), ZERO),
            )
            s1, s2, s3 = float(agg['s1']), float(agg['s2']), float(agg['s3'])

        total_emissions = s1 + s2 + s3
        record_count = qs.count()
        facility_count = qs.values('facility_name').distinct().count()
        avg_quality = qs.aggregate(a=Avg('data_quality_score'))['a'] or 0

        # Bar chart: scope breakdown
        by_scope = [
            {'scope': 'Scope 1', 'value': s1},
            {'scope': 'Scope 2', 'value': s2},
            {'scope': 'Scope 3', 'value': s3},
        ]

        # Line chart: emissions by year
        chart_years = list(qs.order_by('reporting_year').values_list('reporting_year', flat=True).distinct())
        by_year = []
        for y in chart_years:
            yqs = qs.filter(reporting_year=y)
            yagg = yqs.aggregate(
                s1=Coalesce(Sum('scope_1_emissions'), ZERO),
                s2=Coalesce(Sum('scope_2_emissions'), ZERO),
                s3=Coalesce(Sum('scope_3_emissions'), ZERO),
            )
            by_year.append({
                'year': y,
                'scope_1': float(yagg['s1']),
                'scope_2': float(yagg['s2']),
                'scope_3': float(yagg['s3']),
            })

        return Response({
            'total_emissions': round(total_emissions, 2),
            'facility_count': facility_count,
            'record_count': record_count,
            'average_quality_score': round(avg_quality, 1),
            'available_years': available_years,
            'available_facilities': available_facilities,
            'by_scope': by_scope,
            'by_year': by_year,
        })
