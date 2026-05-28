"""
Chunk 2.4: Ingestion Workflow Endpoints - Views

IngestionViewSet:
- POST /api/ingest/upload/ → Upload CSV, create RawIngestion
- POST /api/ingest/{id}/parse/ → Parse CSV into rows
- POST /api/ingest/{id}/normalize/ → Normalize rows, validate
- GET /api/ingest/{id}/status/ → Check progress
- GET /api/ingest/{id}/ → Full details

Each step is idempotent (re-running doesn't create duplicates).
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.db import transaction
import csv
import io
from .models import RawIngestion, ParsedRecord, NormalizedRecord
from .serializers_workflow import (
    IngestionUploadSerializer,
    IngestionStatusSerializer,
    IngestionDetailSerializer,
    IngestionListSerializer,
)
from breathe.apps.emissions.models import DataSource, NormalizedRecord as EmissionsNormalizedRecord
from breathe.apps.review.models import ReviewTask
from breathe.apps.auth.permissions import TenantQuerySetMixin, TenantIsolationPermission, IsDataProvider


class IngestionViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
    """
    Ingestion workflow endpoints.

    Workflow:
    1. POST /api/ingest/upload/ → Save raw CSV
    2. POST /api/ingest/{id}/parse/ → Parse into rows
    3. POST /api/ingest/{id}/normalize/ → Normalize, validate
    4. Status and details at each step

    Design:
    - Each step is idempotent (safe to re-run)
    - Synchronous (no Celery) for MVP
    - Multi-tenant aware (TenantQuerySetMixin)
    """

    queryset = RawIngestion.objects.all()
    permission_classes = [
        permissions.IsAuthenticated,
        TenantIsolationPermission,
        IsDataProvider  # Only data providers can upload/manage ingestions
    ]
    parser_classes = (MultiPartParser, FormParser)

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'upload':
            return IngestionUploadSerializer
        elif self.action == 'status':
            return IngestionStatusSerializer
        elif self.action == 'retrieve':
            return IngestionDetailSerializer
        else:
            return IngestionListSerializer

    # ========================================================================
    # STEP 1: UPLOAD
    # ========================================================================

    @action(detail=False, methods=['post'], parser_classes=(MultiPartParser, FormParser))
    def upload(self, request):
        """
        POST /api/ingest/upload/

        Upload a CSV file.

        Request (multipart/form-data):
        - data_source_id: UUID
        - file: CSV file

        Response:
        {
          "id": "ingestion-1",
          "filename": "emissions_2023.csv",
          "status": "UPLOAD",
          "summary": {
            "total_rows": 0,
            ...
          }
        }

        Idempotency:
        - Same file (same hash) returns same ingestion_id
        - Avoids duplicate uploads
        """
        serializer = IngestionUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_obj = serializer.validated_data['file']
        data_source_id = serializer.validated_data['data_source_id']

        # Read file content
        file_content = file_obj.read()
        if isinstance(file_content, bytes):
            file_content_str = file_content.decode('utf-8')
        else:
            file_content_str = file_content

        # Compute hash for idempotency
        file_hash = RawIngestion.compute_hash(file_content if isinstance(file_content, bytes) else file_content.encode())

        # Check if this file was already uploaded (idempotency)
        existing = RawIngestion.objects.filter(file_hash=file_hash).first()
        if existing:
            return Response(
                {
                    'message': 'File already uploaded',
                    'ingestion_id': str(existing.id),
                    'status': existing.status
                },
                status=status.HTTP_200_OK
            )

        # Create new ingestion
        with transaction.atomic():
            ingestion = RawIngestion.objects.create(
                tenant_id=request.user.profile.tenant_id,
                data_source_id=data_source_id,
                filename=file_obj.name,
                file_hash=file_hash,
                raw_csv_content=file_content_str,
                line_count=len(file_content_str.splitlines()) - 1,  # Exclude header
                file_size=len(file_content) if isinstance(file_content, bytes) else len(file_content.encode()),
                status='UPLOAD',
                uploaded_at=timezone.now()
            )

        serializer = IngestionStatusSerializer(ingestion)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ========================================================================
    # STEP 2: PARSE
    # ========================================================================

    @action(detail=True, methods=['post'])
    def parse(self, request, pk=None):
        """
        POST /api/ingest/{id}/parse/

        Parse CSV into rows.

        Response:
        {
          "id": "ingestion-1",
          "status": "PARSED",
          "summary": {
            "total_rows": 100,
            "parsed_rows": 98,
            ...
          }
        }

        Idempotency:
        - Re-parsing deletes old ParsedRecords and creates new ones
        - Allows recovery from parsing bugs
        """
        ingestion = self.get_object()

        if ingestion.status not in ['UPLOAD', 'PARSED']:
            return Response(
                {'detail': f'Cannot parse from status {ingestion.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Delete old parsed records (idempotency)
            ParsedRecord.objects.filter(ingestion_id=ingestion.id).delete()

            # SAP exports are always semicolon-delimited (European locale).
            # For other sources, sniff the delimiter from the first 2KB.
            source_type = ingestion.data_source_id.source_type
            if source_type == 'SAP':
                delimiter = ';'
                ingestion.dialect_detected = ";-delimited"
            else:
                try:
                    dialect = csv.Sniffer().sniff(ingestion.raw_csv_content[:2048], delimiters=',;\t|')
                    delimiter = dialect.delimiter
                    ingestion.dialect_detected = f"{delimiter}-delimited"
                except Exception:
                    delimiter = ','
                    ingestion.dialect_detected = "auto"

            csv_reader = csv.DictReader(io.StringIO(ingestion.raw_csv_content), delimiter=delimiter)

            parsed_count = 0
            error_count = 0
            row_number = 1

            for row in csv_reader:
                row_number += 1

                # Create parsed record
                parsed_record = ParsedRecord.objects.create(
                    ingestion_id=ingestion,
                    tenant_id=request.user.profile.tenant_id,
                    source_row_number=row_number,
                    raw_values=dict(row),
                    parsing_errors=[]
                )
                parsed_count += 1

            # Update ingestion
            ingestion.status = 'PARSED'
            ingestion.parsed_rows = parsed_count
            ingestion.total_rows = parsed_count
            ingestion.parsed_at = timezone.now()
            ingestion.save()

        serializer = IngestionStatusSerializer(ingestion)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ========================================================================
    # STEP 3: NORMALIZE
    # ========================================================================

    @action(detail=True, methods=['post'])
    def normalize(self, request, pk=None):
        """
        POST /api/ingest/{id}/normalize/

        Normalize parsed rows and validate.

        Creates:
        - NormalizedRecord (ingest model)
        - EmissionsDataPoint (with is_valid flag)
        - ReviewTask (for analyst review)

        Response:
        {
          "id": "ingestion-1",
          "status": "NORMALIZED",
          "summary": {
            "total_rows": 100,
            "parsed_rows": 100,
            "valid_rows": 95,
            "rows_with_warnings": 3,
            "rows_with_errors": 2
          }
        }

        Idempotency:
        - Re-normalizing deletes old NormalizedRecords
        - Uses updated validation logic
        """
        ingestion = self.get_object()

        if ingestion.status not in ['PARSED', 'NORMALIZED']:
            return Response(
                {'detail': f'Cannot normalize from status {ingestion.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            from .normalization import normalize_ingestion
            result = normalize_ingestion(ingestion)

            ingestion.status = 'NORMALIZED'
            ingestion.valid_rows = result['valid_count']
            ingestion.rows_with_warnings = 0
            ingestion.rows_with_errors = result['invalid_count']
            ingestion.normalized_at = timezone.now()
            ingestion.field_mapping_used = ingestion.data_source_id.field_mapping
            ingestion.save()

        serializer = IngestionStatusSerializer(ingestion)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ========================================================================
    # STATUS AND DETAILS
    # ========================================================================

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        GET /api/ingest/{id}/status/

        Get current progress of ingestion.

        Response:
        {
          "id": "ingestion-1",
          "status": "NORMALIZED",
          "steps_completed": ["upload", "parse", "normalize"],
          "summary": {
            "total_rows": 100,
            "parsed_rows": 100,
            "valid_rows": 95,
            "rows_with_warnings": 3,
            "rows_with_errors": 2,
            "error_rows": 5,
            "success_rate": 95.0
          },
          "completed_percentage": 75
        }
        """
        ingestion = self.get_object()
        serializer = IngestionStatusSerializer(ingestion)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        """
        GET /api/ingest/{id}/

        Get full details including sample records with errors.
        """
        ingestion = self.get_object()
        serializer = IngestionDetailSerializer(ingestion, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def list(self, request):
        """
        GET /api/ingest/

        List all ingestions for this user's tenant.
        """
        queryset = self.get_queryset()
        serializer = IngestionListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
