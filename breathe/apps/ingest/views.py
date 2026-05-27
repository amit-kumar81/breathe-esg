"""
Views for ingest endpoints.

Chunk 1.2:
- POST /api/ingest/upload/ - Accept CSV file upload, return ingestion_id

Design:
- No async/Celery yet (synchronous for MVP)
- File stored in DB (JSONB) for full auditability
- Idempotency: same file hash = same ingestion_id returned
- Multi-tenancy: validated at view level (placeholder for now)
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework import generics
from .models import RawIngestion, DataSource
from .serializers import IngestionUploadSerializer, RawIngestionListSerializer, RawIngestionDetailSerializer, DataSourceSerializer
from .utils import compute_file_hash, parse_csv_to_rows, check_idempotency

logger = logging.getLogger('breathe.ingest')


class IngestionViewSet(viewsets.ViewSet):
    """
    ViewSet for ingestion operations.

    Endpoints:
    - POST /api/ingest/upload/ - Upload CSV file
    - GET /api/ingest/ - List ingestions (future)
    - GET /api/ingest/{id}/ - Get ingestion details (future)
    """
    parser_classes = (MultiPartParser, FormParser)

    @action(detail=False, methods=['post'], url_path='upload', url_name='upload')
    def upload(self, request):
        """
        Upload a CSV file for emissions data ingestion.

        Request body (multipart/form-data):
        - file: CSV file (required)
        - data_source_id: UUID (required)
        - description: string (optional)

        Response (201 Created):
        {
            "ingestion_id": "uuid",
            "status": "received",
            "filename": "data.csv",
            "line_count": 100,
            "file_hash": "sha256hash",
            "message": "File uploaded successfully"
        }

        Error responses:
        - 400: Invalid request (bad CSV, missing fields, etc.)
        - 404: DataSource not found
        """
        # Validate serializer
        serializer = IngestionUploadSerializer(
            data=request.data,
            context={'request': request}
        )

        if not serializer.is_valid():
            logger.warning(f"Upload validation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get validated data
        validated_data = serializer.validated_data
        file_obj = validated_data['file']
        data_source = validated_data['_data_source']
        parsed_rows = validated_data['_parsed_rows']

        # Compute file hash
        file_hash = compute_file_hash(file_obj)
        logger.info(f"File hash: {file_hash}")

        # Check idempotency: has this file been uploaded before?
        existing_ingestion = check_idempotency(file_hash, data_source.tenant_id)
        if existing_ingestion:
            logger.info(f"File already uploaded, returning existing ingestion: {existing_ingestion.id}")
            return Response(
                {
                    "ingestion_id": str(existing_ingestion.id),
                    "status": "already_received",
                    "filename": existing_ingestion.filename,
                    "line_count": existing_ingestion.line_count,
                    "file_hash": existing_ingestion.file_hash,
                    "message": "This file was already uploaded previously. Returning existing ingestion."
                },
                status=status.HTTP_200_OK
            )

        # Create RawIngestion record
        try:
            # Get original CSV content (source of truth)
            file_obj.seek(0)
            csv_text_content = file_obj.read().decode('utf-8')
            file_obj.seek(0)

            # Note: We only store raw_csv_content (the original text)
            # Parsing happens on-demand in Chunk 1.3
            # This avoids any risk of data loss from parsing
            raw_ingestion = RawIngestion.objects.create(
                tenant_id=data_source.tenant_id,
                data_source_id=data_source,
                filename=file_obj.name,
                file_hash=file_hash,
                line_count=len(parsed_rows),  # Count from validation parse, not stored in DB
                raw_csv_content=csv_text_content  # Single source of truth
            )
            logger.info(f"Created RawIngestion: {raw_ingestion.id} ({len(parsed_rows)} rows)")

            return Response(
                {
                    "ingestion_id": str(raw_ingestion.id),
                    "status": "received",
                    "filename": raw_ingestion.filename,
                    "line_count": raw_ingestion.line_count,
                    "file_hash": raw_ingestion.file_hash,
                    "message": "File uploaded successfully"
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Error creating RawIngestion: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Upload failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def list(self, request):
        return Response({"message": "List endpoint coming in Chunk 2.1"})

    def retrieve(self, request, pk=None):
        return Response({"message": "Retrieve endpoint coming in Chunk 2.1"})

    @action(detail=True, methods=['post'], url_path='parse', url_name='parse')
    def parse(self, request, pk=None):
        """
        Parse a RawIngestion into ParsedRecords.

        Endpoint: POST /api/ingest/{ingestion_id}/parse/

        Process:
        1. Get RawIngestion by ID
        2. Verify it exists (return 404 if not)
        3. Tenant isolation placeholder (Chunk 2.3 will add real check)
        4. Parse rows: create ParsedRecord for each row
        5. Return summary of parsing operation

        Response (200 OK):
        {
            "ingestion_id": "uuid",
            "status": "parsed",
            "total_rows": 100,
            "parsed_records_created": 100,
            "empty_rows": 0,
            "parsing_errors": [],
            "message": "Successfully parsed 100 rows"
        }

        Idempotency:
        - If called twice, existing ParsedRecords are deleted and recreated
        - This allows re-parsing if logic changes
        - Result is deterministic: same raw_content = same ParsedRecords
        """
        from .models import RawIngestion
        from .utils import parse_raw_ingestion

        # Get RawIngestion
        try:
            raw_ingestion = RawIngestion.objects.get(id=pk)
        except RawIngestion.DoesNotExist:
            logger.warning(f"RawIngestion not found: {pk}")
            return Response(
                {"error": "RawIngestion not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Tenant isolation placeholder
        # In Chunk 2.3, we'll verify request.user.tenant_id == raw_ingestion.tenant_id
        if not hasattr(request, 'tenant_id'):
            pass  # Allow for now

        # Parse the ingestion
        logger.info(f"Starting parse for ingestion {raw_ingestion.id}")
        try:
            result = parse_raw_ingestion(raw_ingestion)

            total_rows = raw_ingestion.line_count
            parsed_count = result['parsed_count']
            parsing_errors = result['parsing_errors']
            empty_rows = []

            logger.info(f"Parse complete: {parsed_count} parsed, {len(parsing_errors)} errors")

            return Response(
                {
                    "ingestion_id": str(raw_ingestion.id),
                    "status": "parsed",
                    "total_rows": total_rows,
                    "parsed_records_created": parsed_count,
                    "empty_rows": len(empty_rows),
                    "parsing_errors": parsing_errors,
                    "message": f"Successfully parsed {parsed_count} of {total_rows} rows"
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error parsing ingestion {pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to parse ingestion. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='normalize', url_name='normalize')
    def normalize(self, request, pk=None):
        """
        Normalize a RawIngestion into NormalizedRecords.

        Chunk 1.4: Schema Definition & Normalization Rules

        Endpoint: POST /api/ingest/{ingestion_id}/normalize/

        Process:
        1. Get RawIngestion by ID
        2. Verify it exists (return 404 if not)
        3. Get all ParsedRecords for this ingestion
        4. Apply DataSource.field_mapping to map CSV columns to standard fields
        5. Validate each field (facility_name, scope_1_emissions, reporting_year, etc.)
        6. Create NormalizedRecord for each ParsedRecord with validation results
        7. Return summary of normalization operation

        Response (200 OK):
        {
            "ingestion_id": "uuid",
            "status": "normalized",
            "total_parsed_records": 100,
            "total_normalized_records": 100,
            "valid_records_count": 95,
            "invalid_records_count": 5,
            "normalization_errors": [],
            "message": "Successfully normalized 100 records (95 valid, 5 invalid)"
        }

        Idempotency:
        - If called twice, existing NormalizedRecords are deleted and recreated
        - This allows re-normalization if validation logic changes
        - Result is deterministic: same ParsedRecords = same NormalizedRecords
        """
        from .models import RawIngestion
        from .normalization import normalize_ingestion

        # Get RawIngestion
        try:
            raw_ingestion = RawIngestion.objects.get(id=pk)
        except RawIngestion.DoesNotExist:
            logger.warning(f"RawIngestion not found: {pk}")
            return Response(
                {"error": "RawIngestion not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Tenant isolation placeholder
        # In Chunk 2.3, we'll verify request.user.tenant_id == raw_ingestion.tenant_id
        if not hasattr(request, 'tenant_id'):
            pass  # Allow for now

        # Check that ParsedRecords exist
        from .models import ParsedRecord
        parsed_count = ParsedRecord.objects.filter(ingestion_id=raw_ingestion).count()
        if parsed_count == 0:
            logger.warning(f"No ParsedRecords found for ingestion {raw_ingestion.id}")
            return Response(
                {"error": "No ParsedRecords found. Call /parse/ first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Normalize the ingestion
        logger.info(f"Starting normalization for ingestion {raw_ingestion.id}")
        try:
            result = normalize_ingestion(raw_ingestion)

            total_parsed = result['total_parsed']
            total_normalized = result['total_normalized']
            valid_count = result['valid_count']
            invalid_count = result['invalid_count']
            normalization_errors = result['normalization_errors']

            logger.info(
                f"Normalization complete: {total_normalized} normalized, "
                f"{valid_count} valid, {invalid_count} invalid"
            )

            return Response(
                {
                    "ingestion_id": str(raw_ingestion.id),
                    "status": "normalized",
                    "total_parsed_records": total_parsed,
                    "total_normalized_records": total_normalized,
                    "valid_records_count": valid_count,
                    "invalid_records_count": invalid_count,
                    "normalization_errors": normalization_errors,
                    "message": f"Successfully normalized {total_normalized} records ({valid_count} valid, {invalid_count} invalid)"
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error normalizing ingestion {pk}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to normalize ingestion. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DataSourceListView(generics.ListAPIView):
    """GET /api/ingest/datasources/ — list data sources for the current tenant."""
    serializer_class = DataSourceSerializer

    def get_queryset(self):
        tenant_id = self.request.user.profile.tenant_id
        return DataSource.objects.filter(tenant_id=tenant_id).order_by('name')
