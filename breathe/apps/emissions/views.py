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
from django.db.models import Avg, Sum

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

        Returns summary statistics for all EmissionsDataPoints.
        """
        queryset = self.get_queryset()

        # Count by scope
        by_scope = {}
        for scope_choice in ['SCOPE_1', 'SCOPE_2', 'SCOPE_3']:
            by_scope[scope_choice] = queryset.filter(scope=scope_choice).count()

        # Count by year
        years_qs = (
            queryset.values_list('year', flat=True)
            .distinct()
            .order_by('-year')
        )
        by_year = {
            str(y): queryset.filter(year=y).count()
            for y in years_qs if y
        }

        # Total emissions by scope
        total_scope1 = queryset.filter(scope='SCOPE_1').aggregate(
            total=Sum('emissions_value')
        )['total'] or 0
        total_scope2 = queryset.filter(scope='SCOPE_2').aggregate(
            total=Sum('emissions_value')
        )['total'] or 0
        total_scope3 = queryset.filter(scope='SCOPE_3').aggregate(
            total=Sum('emissions_value')
        )['total'] or 0

        return Response({
            'total_records': queryset.count(),
            'valid_records': queryset.filter(is_valid=True).count(),
            'invalid_records': queryset.filter(is_valid=False).count(),
            'by_scope': by_scope,
            'by_year': by_year,
            'total_scope1_mtco2e': float(total_scope1),
            'total_scope2_mtco2e': float(total_scope2),
            'total_scope3_mtco2e': float(total_scope3),
        })

