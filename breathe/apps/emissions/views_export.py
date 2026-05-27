"""
Chunk 2.5: Data Export & Reporting - Views

Export endpoints for emissions data:
- GET /api/emissions/export/ - Export filtered records as CSV/JSON
- GET /api/emissions/summary/ - Summary statistics for dashboard
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
import csv
import json
from io import StringIO
from .models import EmissionsDataPoint
from .serializers_export import (
    EmissionsExportSerializer,
    ReportingSummarySerializer,
    ExportMetadataSerializer
)
from breathe.apps.auth.permissions import TenantQuerySetMixin, TenantIsolationPermission
from rest_framework import permissions


class EmissionsExportViewSet(TenantQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Export and reporting endpoints for emissions data.

    Endpoints:
    - GET /api/emissions/export/ - Download CSV/JSON
    - GET /api/emissions/summary/ - Dashboard statistics
    """
    queryset = EmissionsDataPoint.objects.all()
    permission_classes = [
        permissions.IsAuthenticated,
        TenantIsolationPermission
    ]
    serializer_class = EmissionsExportSerializer

    # ========================================================================
    # EXPORT ENDPOINT
    # ========================================================================

    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        GET /api/emissions/export/?format=csv&year=2023&status=APPROVED

        Export filtered emissions records.

        Query Parameters:
        - format: 'csv' or 'json' (default: json)
        - year: Filter by reporting year (optional)
        - status: Filter by review status - APPROVED, REJECTED, PENDING (optional)

        Response:
        - CSV: File download (application/csv)
        - JSON: Metadata + records array

        Examples:
        GET /api/emissions/export/?format=csv
        → Download all approved records as CSV

        GET /api/emissions/export/?format=json&year=2023&status=APPROVED
        → JSON with 2023 records that are approved
        """

        # Get query parameters
        export_format = request.query_params.get('format', 'json').lower()
        year = request.query_params.get('year')
        status_filter = request.query_params.get('status')

        # Validate format
        if export_format not in ['csv', 'json']:
            return Response(
                {'detail': 'format must be "csv" or "json"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build queryset with filters
        queryset = self.get_queryset()

        # Filter by year
        if year:
            try:
                year = int(year)
                queryset = queryset.filter(
                    normalized_record__normalized_values__reporting_year=year
                )
            except ValueError:
                return Response(
                    {'detail': 'year must be an integer'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Filter by status
        if status_filter:
            if status_filter not in ['APPROVED', 'REJECTED', 'PENDING']:
                return Response(
                    {'detail': 'status must be APPROVED, REJECTED, or PENDING'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            queryset = queryset.filter(review_status=status_filter)
        else:
            # Default: only approved records
            queryset = queryset.filter(review_status='APPROVED')

        # Serialize records
        serializer = EmissionsExportSerializer(queryset, many=True)
        records = serializer.data

        if export_format == 'csv':
            return self._export_csv(records, request)
        else:  # json
            return self._export_json(records, request)

    def _export_csv(self, records, request):
        """
        Export records as CSV file.

        Format:
        - Header row with column names
        - Data rows with all values
        - Properly formatted decimals
        """
        if not records:
            return Response(
                {'detail': 'No records to export'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create CSV
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                'Facility',
                'Scope 1 Emissions (tCO2e)',
                'Scope 2 Emissions (tCO2e)',
                'Scope 3 Emissions (tCO2e)',
                'Year',
                'Status',
                'Quality Score',
                'Approved By',
                'Export Date'
            ]
        )

        writer.writeheader()

        export_date = timezone.now().strftime('%Y-%m-%d %H:%M:%S')

        for record in records:
            writer.writerow({
                'Facility': record.get('facility_name', ''),
                'Scope 1 Emissions (tCO2e)': record.get('scope_1_emissions') or '',
                'Scope 2 Emissions (tCO2e)': record.get('scope_2_emissions') or '',
                'Scope 3 Emissions (tCO2e)': record.get('scope_3_emissions') or '',
                'Year': record.get('reporting_year') or '',
                'Status': record.get('review_status', ''),
                'Quality Score': record.get('data_quality_score', ''),
                'Approved By': record.get('analyst_name') or '',
                'Export Date': export_date
            })

        # Create HTTP response
        response = HttpResponse(
            output.getvalue(),
            content_type='text/csv'
        )
        response['Content-Disposition'] = 'attachment; filename="emissions_export.csv"'

        return response

    def _export_json(self, records, request):
        """
        Export records as JSON with metadata.

        Format:
        {
          "metadata": {
            "export_timestamp": "...",
            "tenant_name": "...",
            "record_count": 100,
            "filters_applied": {"year": 2023, "status": "APPROVED"}
          },
          "records": [...]
        }
        """
        # Build filters dict for metadata
        filters = {}
        if request.query_params.get('year'):
            filters['year'] = int(request.query_params.get('year'))
        if request.query_params.get('status'):
            filters['status'] = request.query_params.get('status')

        # Get tenant name
        try:
            tenant_name = request.user.profile.tenant.name
        except Exception:
            tenant_name = 'Unknown'

        # Build metadata
        metadata = {
            'export_timestamp': timezone.now().isoformat(),
            'export_format': 'json',
            'tenant_name': tenant_name,
            'record_count': len(records),
            'filters_applied': filters,
            'generated_by': request.user.username
        }

        return Response(
            {
                'metadata': metadata,
                'records': records
            },
            status=status.HTTP_200_OK
        )

    # ========================================================================
    # SUMMARY/REPORTING ENDPOINT
    # ========================================================================

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        GET /api/emissions/summary/

        Get summary statistics for dashboard.

        Returns:
        - Total records
        - Count by status (APPROVED, PENDING, REJECTED)
        - Count by year
        - Count by facility
        - Count by quality tier (0-40, 40-70, 70-80, 80-100)
        - Average quality score
        - Average/total emissions by scope
        """

        queryset = self.get_queryset()

        # Total counts
        total_records = queryset.count()
        approved = queryset.filter(review_status='APPROVED').count()
        pending = queryset.filter(review_status='PENDING').count()
        rejected = queryset.filter(review_status='REJECTED').count()
        auto_approved = queryset.filter(review_status='AUTO_APPROVED').count()

        # By status
        by_status = {
            'APPROVED': approved,
            'PENDING': pending,
            'REJECTED': rejected,
            'AUTO_APPROVED': auto_approved
        }

        # By year (from normalized_values)
        by_year = {}
        for record in queryset.values('normalized_record__normalized_values__reporting_year').annotate(count=Count('id')):
            year = record['normalized_record__normalized_values__reporting_year']
            if year:
                by_year[str(year)] = record['count']

        # By facility (from normalized_values)
        by_facility = {}
        for record in queryset.values('normalized_record__normalized_values__facility_name').annotate(count=Count('id')):
            facility = record['normalized_record__normalized_values__facility_name']
            if facility:
                by_facility[facility] = record['count']

        # By quality tier
        by_quality_tier = {
            '0-40': queryset.filter(data_quality_score__lt=40).count(),
            '40-70': queryset.filter(data_quality_score__gte=40, data_quality_score__lt=70).count(),
            '70-80': queryset.filter(data_quality_score__gte=70, data_quality_score__lt=80).count(),
            '80-100': queryset.filter(data_quality_score__gte=80).count()
        }

        # Averages
        avg_quality = queryset.aggregate(Avg('data_quality_score'))['data_quality_score__avg'] or 0

        # Scope emissions (approximation from normalized_values)
        # Note: In production, would store these in indexed columns
        total_scope_1 = 0
        total_scope_2 = 0
        total_scope_3 = 0

        for record in queryset:
            try:
                s1 = record.normalized_record.normalized_values.get('scope_1_emissions', 0)
                s2 = record.normalized_record.normalized_values.get('scope_2_emissions', 0)
                s3 = record.normalized_record.normalized_values.get('scope_3_emissions', 0)

                total_scope_1 += float(s1) if s1 else 0
                total_scope_2 += float(s2) if s2 else 0
                total_scope_3 += float(s3) if s3 else 0
            except Exception:
                pass

        total_emissions = total_scope_1 + total_scope_2 + total_scope_3
        avg_scope_1 = total_scope_1 / total_records if total_records > 0 else 0
        avg_scope_2 = total_scope_2 / total_records if total_records > 0 else 0
        avg_scope_3 = total_scope_3 / total_records if total_records > 0 else 0

        summary_data = {
            'total_records': total_records,
            'approved_records': approved,
            'pending_records': pending,
            'rejected_records': rejected,
            'auto_approved_records': auto_approved,
            'by_status': by_status,
            'by_year': by_year,
            'by_facility': by_facility,
            'by_quality_tier': by_quality_tier,
            'average_quality_score': round(avg_quality, 2),
            'average_scope_1': round(avg_scope_1, 2),
            'average_scope_2': round(avg_scope_2, 2),
            'average_scope_3': round(avg_scope_3, 2),
            'total_scope_1': round(total_scope_1, 2),
            'total_scope_2': round(total_scope_2, 2),
            'total_scope_3': round(total_scope_3, 2),
            'total_emissions': round(total_emissions, 2)
        }

        serializer = ReportingSummarySerializer(summary_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
