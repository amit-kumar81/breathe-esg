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
        Supports filtering by: year, review_status, data_source, facility_name
        Supports sorting by: created_at, data_quality_score, year
    
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
    search_fields = ['normalized_values__facility_name']
    ordering_fields = ['created_at', 'data_quality_score', 'normalized_values__year']
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
        
        Returns summary statistics for all EmissionsDataPoints:
        - Total records
        - By review_status
        - By data_quality_score ranges
        - By year
        """
        queryset = self.get_queryset()
        
        # Count by status
        by_status = {}
        for status_choice in ['PENDING', 'APPROVED', 'REJECTED']:
            by_status[status_choice] = queryset.filter(review_status=status_choice).count()
        
        # Count by data quality score range
        quality_ranges = {
            '0-20': queryset.filter(data_quality_score__gte=0, data_quality_score__lt=20).count(),
            '20-40': queryset.filter(data_quality_score__gte=20, data_quality_score__lt=40).count(),
            '40-60': queryset.filter(data_quality_score__gte=40, data_quality_score__lt=60).count(),
            '60-80': queryset.filter(data_quality_score__gte=60, data_quality_score__lt=80).count(),
            '80-100': queryset.filter(data_quality_score__gte=80, data_quality_score__lte=100).count(),
        }
        
        # Count by year (from normalized_values)
        years = queryset.values_list(
            'normalized_values__year',
            flat=True
        ).distinct().order_by('-normalized_values__year')
        
        by_year = {}
        for year in years:
            if year:
                by_year[str(int(year))] = queryset.filter(
                    normalized_values__year=year
                ).count()
        
        return Response({
            'total_records': queryset.count(),
            'by_status': by_status,
            'by_data_quality': quality_ranges,
            'by_year': by_year,
            'average_quality_score': queryset.aggregate(
                avg_score=__import__('django.db.models', fromlist=['Avg']).Avg('data_quality_score')
            )['avg_score'] or 0
        })

