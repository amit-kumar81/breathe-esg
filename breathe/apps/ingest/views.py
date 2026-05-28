"""Ingest views: upload, parse, normalize, list, detail."""

import logging
from django.db.models import F, Count
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework import generics
from .models import RawIngestion, DataSource
from .serializers import IngestionUploadSerializer, RawIngestionListSerializer, RawIngestionDetailSerializer, DataSourceSerializer
from .utils import compute_file_hash, parse_csv_to_rows, check_idempotency
from breathe.apps.auth.permissions import IsDataProvider

logger = logging.getLogger('breathe.ingest')


class IngestionViewSet(viewsets.ViewSet):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsDataProvider]

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
        try:
            rows = list(
                RawIngestion.objects
                .annotate(
                    parsed_count=Count('parsed_records', distinct=True),
                    normalized_count=Count('normalized_records', distinct=True),
                    ds_name=F('data_source_id__name')
                )
                .order_by('-created_at')
                .values('id', 'filename', 'line_count', 'created_at',
                        'parsed_count', 'normalized_count', 'ds_name')
            )
            data = []
            for r in rows:
                if r['normalized_count'] > 0:
                    step = 'NORMALIZED'
                elif r['parsed_count'] > 0:
                    step = 'PARSED'
                else:
                    step = 'UPLOADED'
                data.append({
                    'id': str(r['id']),
                    'filename': r['filename'],
                    'line_count': r['line_count'],
                    'step': step,
                    'data_source_name': r['ds_name'] or '—',
                    'created_at': r['created_at'].isoformat(),
                })
            return Response({'results': data, 'count': len(data)})
        except Exception as e:
            logger.error(f"Error listing ingestions: {e}", exc_info=True)
            return Response({'results': [], 'count': 0, '_error': str(e)}, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        try:
            ingestion = RawIngestion.objects.get(id=pk)
        except RawIngestion.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        from .models import ParsedRecord, NormalizedRecord as IngestNormalized
        parsed_count = ParsedRecord.objects.filter(ingestion_id=ingestion).count()
        normalized_count = IngestNormalized.objects.filter(ingestion_id=ingestion).count()

        if normalized_count > 0:
            step = 'NORMALIZED'
            completion_percentage = 100
        elif parsed_count > 0:
            step = 'PARSED'
            completion_percentage = 66
        else:
            step = 'UPLOADED'
            completion_percentage = 33

        sample_parsed = list(
            ParsedRecord.objects.filter(ingestion_id=ingestion)
            .order_by('source_row_number')
            .values('source_row_number', 'raw_values', 'parsing_errors')[:5]
        )
        sample_normalized = list(
            IngestNormalized.objects.filter(ingestion_id=ingestion)
            .values('facility_name', 'scope_1_emissions', 'scope_2_emissions',
                    'scope_3_emissions', 'reporting_year',
                    'data_quality_score', 'is_valid', 'validation_errors')[:5]
        )
        # Decimal fields come back as Decimal objects — convert to float for JSON
        for rec in sample_normalized:
            for field in ('scope_1_emissions', 'scope_2_emissions', 'scope_3_emissions'):
                if rec[field] is not None:
                    rec[field] = float(rec[field])
        valid_count = IngestNormalized.objects.filter(ingestion_id=ingestion, is_valid=True).count()

        # Read CSV column order from source of truth.
        # SAP files are semicolon-delimited; all others use sniffer.
        import csv as csv_module, io as io_module
        csv_columns = []
        if ingestion.raw_csv_content:
            source_type = ingestion.data_source_id.source_type
            if source_type == 'SAP':
                delimiter = ';'
            else:
                try:
                    sniffer = csv_module.Sniffer()
                    dialect = sniffer.sniff(ingestion.raw_csv_content[:2048], delimiters=',;\t|')
                    delimiter = dialect.delimiter
                except Exception:
                    delimiter = ','
            reader = csv_module.reader(io_module.StringIO(ingestion.raw_csv_content), delimiter=delimiter)
            csv_columns = next(reader, [])

        data_source = ingestion.data_source_id
        return Response({
            'id': str(ingestion.id),
            'filename': ingestion.filename,
            'line_count': ingestion.line_count,
            'step': step,
            'completion_percentage': completion_percentage,
            'csv_columns': csv_columns,
            'data_source_id': str(data_source.id),
            'data_source_name': data_source.name,
            'data_source_type': data_source.source_type,
            'sample_parsed_records': sample_parsed,
            'sample_normalized_records': sample_normalized,
            'summary': {
                'total_records': normalized_count,
                'valid_records': valid_count,
                'warning_records': 0,
                'error_records': normalized_count - valid_count,
            } if normalized_count > 0 else None,
        })

    @action(detail=True, methods=['post'], url_path='parse', url_name='parse')
    def parse(self, request, pk=None):
        """POST /api/ingest/{id}/parse/ — parse CSV rows into ParsedRecords."""
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

        # Parse the ingestion (source-type aware: SAP always uses semicolon)
        logger.info(f"Starting parse for ingestion {raw_ingestion.id}")
        try:
            result = parse_raw_ingestion(raw_ingestion, source_type=raw_ingestion.data_source_id.source_type)

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
        """POST /api/ingest/{id}/normalize/ — normalize all ParsedRecords for this ingestion."""
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
                {"error": f"Normalization failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DataSourceListView(generics.ListAPIView):
    serializer_class = DataSourceSerializer
    permission_classes = [IsDataProvider]

    def get_queryset(self):
        tenant_id = self.request.user.profile.tenant_id
        return DataSource.objects.filter(tenant_id=tenant_id).order_by('name')
