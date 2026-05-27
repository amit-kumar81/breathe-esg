"""
ViewSets for EmissionsDataPoint API endpoints.

Chunk 2.1: Django REST Framework Setup & Serializers

Endpoints:
- GET /api/emissions/ → list with filtering
- GET /api/emissions/{id}/ → detail with audit trail
- GET /api/emissions/{id}/audit/ → audit trail for record
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Avg, Sum, Count

from breathe.apps.emissions.models import EmissionsDataPoint
from breathe.apps.emissions.serializers import (
    EmissionsDataPointListSerializer,
    EmissionsDataPointDetailSerializer,
    AuditLogSerializer
)
from breathe.apps.emissions.filters import EmissionsDataPointFilter
from breathe.apps.audit.models import AuditLog


class EmissionsDataPointViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for EmissionsDataPoint CRUD operations.

    List endpoint:
        GET /api/emissions/
        Supports filtering by: year, scope, data_source, facility_name
        Supports sorting by: created_at, year, emissions_value

    Detail endpoint:
        GET /api/emissions/{id}/
        Returns full record with audit trail

    Audit endpoint:
        GET /api/emissions/{id}/audit/
        Returns audit trail for this record
    """

    queryset = EmissionsDataPoint.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EmissionsDataPointFilter
    search_fields = ['facility_name']
    ordering_fields = ['created_at', 'year', 'emissions_value']
    ordering = ['-created_at']  # Default: newest first
    
    def get_serializer_class(self):
        """
        Use lightweight serializer for list, detailed serializer for retrieve.
        """
        if self.action == 'retrieve':
            return EmissionsDataPointDetailSerializer
        return EmissionsDataPointListSerializer
    
    def get_queryset(self):
        """
        Filter by tenant (multi-tenancy).
        Only return records for the current user's tenant.
        
        Note: In Chunk 2.3, this will be enforced via TenantAwareManager.
        For now, return all (will be scoped in production).
        """
        queryset = super().get_queryset()
        
        # TODO: After Chunk 2.3 (Multi-Tenancy)
        # if hasattr(self.request, 'user') and self.request.user.is_authenticated:
        #     queryset = queryset.filter(tenant_id=self.request.user.profile.tenant_id)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def audit(self, request, pk=None):
        """
        GET /api/emissions/{id}/audit/
        
        Returns audit trail for this EmissionsDataPoint.
        Shows all changes: CREATE, UPDATE, DELETE with timestamps and users.
        """
        emissions_point = self.get_object()
        
        # Query audit logs for this record
        audit_logs = AuditLog.objects.filter(
            object_type='EmissionsDataPoint',
            object_id=str(emissions_point.id)
        ).order_by('-timestamp')
        
        # Serialize
        serializer = AuditLogSerializer(audit_logs, many=True)
        
        return Response({
            'emissions_data_point_id': str(emissions_point.id),
            'facility_name': emissions_point.normalized_values.get('facility_name'),
            'total_changes': audit_logs.count(),
            'audit_trail': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        GET /api/emissions/summary/
        Optional query params: year, facility_name, scope (SCOPE_1/SCOPE_2/SCOPE_3)

        Returns summary statistics shaped for the dashboard charts.
        available_years and available_facilities always return the full
        unfiltered set so the dropdowns stay populated.
        """
        all_qs = self.get_queryset()

        # available_years / available_facilities always show everything
        available_years = list(
            all_qs.order_by('year').values_list('year', flat=True).distinct()
        )
        available_facilities = sorted(
            all_qs.order_by('facility_name')
            .values_list('facility_name', flat=True)
            .distinct()
        )

        # Apply filters to the metrics queryset
        queryset = all_qs
        year = request.query_params.get('year')
        facility_name = request.query_params.get('facility_name')
        scope = request.query_params.get('scope')

        if year:
            queryset = queryset.filter(year=int(year))
        if facility_name:
            queryset = queryset.filter(facility_name=facility_name)
        if scope:
            queryset = queryset.filter(scope=scope)

        total_emissions = queryset.aggregate(t=Sum('emissions_value'))['t'] or 0
        record_count = queryset.count()
        valid_count = queryset.filter(is_valid=True).count()
        facility_count = queryset.order_by('facility_name').values('facility_name').distinct().count()
        average_quality_score = round(valid_count / record_count * 100, 1) if record_count else 0

        # Bar chart: [{scope, value}] — respect scope filter
        scope_labels = [('SCOPE_1', 'Scope 1'), ('SCOPE_2', 'Scope 2'), ('SCOPE_3', 'Scope 3')]
        by_scope = [
            {
                'scope': label,
                'value': float(queryset.filter(scope=code).aggregate(t=Sum('emissions_value'))['t'] or 0)
            }
            for code, label in scope_labels
        ]

        # Line chart: [{year, scope_1, scope_2, scope_3}]
        chart_years = list(queryset.order_by('year').values_list('year', flat=True).distinct())
        by_year = []
        for y in chart_years:
            year_qs = queryset.filter(year=y)
            by_year.append({
                'year': y,
                'scope_1': float(year_qs.filter(scope='SCOPE_1').aggregate(t=Sum('emissions_value'))['t'] or 0),
                'scope_2': float(year_qs.filter(scope='SCOPE_2').aggregate(t=Sum('emissions_value'))['t'] or 0),
                'scope_3': float(year_qs.filter(scope='SCOPE_3').aggregate(t=Sum('emissions_value'))['t'] or 0),
            })

        return Response({
            'total_emissions': float(total_emissions),
            'facility_count': facility_count,
            'record_count': record_count,
            'average_quality_score': average_quality_score,
            'available_years': available_years,
            'available_facilities': available_facilities,
            'by_scope': by_scope,
            'by_year': by_year,
        })

