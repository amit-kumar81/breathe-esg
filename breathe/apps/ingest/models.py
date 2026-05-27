"""
Ingest models for raw data reception.

Design Philosophy:
- RawIngestion stores unprocessed data exactly as received (no loss of information).
- ParsedRecord converts raw rows into structured dictionaries (still unvalidated).
- Both use JSONB for flexibility; relational keys for fast querying.
- Tenant isolation via tenant_id foreign key on every model.
"""

import uuid
import hashlib
from django.db import models
from breathe.apps.tenants.models import Tenant


class DataSource(models.Model):
    """
    Metadata about where data is coming from (file upload, API, form, etc.).
    Tracks ingestion source and mapping for normalization.
    """
    SOURCE_TYPES = (
        ('SAP', 'SAP CSV Export'),
        ('UTILITY', 'Utility Portal CSV Export'),
        ('TRAVEL', 'Travel (Concur/Navan) CSV Export'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='data_sources')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    name = models.CharField(max_length=255, help_text="Human-readable name for this source")
    description = models.TextField(blank=True, null=True)
    # Field mapping: source column name -> normalized field name
    # Example: {"Plant_Name": "facility_name", "Metric_Tons_CO2": "scope_1_emissions"}
    field_mapping = models.JSONField(default=dict, help_text="CSV column to normalized field mapping")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ingest_data_source'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant_id']),
            models.Index(fields=['source_type']),
        ]
        unique_together = [['tenant_id', 'name']]

    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"


class RawIngestion(models.Model):
    """
    Raw data as received from the data source.
    Stored as original CSV text—SINGLE SOURCE OF TRUTH.

    Design Philosophy: Pure Relational (Option 1)
    - raw_csv_content: Original CSV file text (never modified)
    - Parsing happens on-demand in Chunk 1.3
    - No data loss, no mismatch between formats

    Why not JSONB cache?
    - If we cache parsed rows, they could become stale
    - If parsing is lossy, original and cache could mismatch
    - Single source of truth (CSV) is simpler, safer
    - ParsedRecords created in Chunk 1.3 become the "parsed cache"
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='raw_ingestions')
    data_source_id = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='ingestions')

    # --- SINGLE SOURCE OF TRUTH ---
    # Original CSV file as TEXT (unparsed, exactly as uploaded)
    # Example: "Plant_Name,Scope1,Year\nPlant A,1000,2023\nPlant B,2000,2023"
    # This is immutable after creation—can always be re-parsed
    raw_csv_content = models.TextField(help_text="Original CSV file content as text (never modified, source of truth)")

    # Metadata
    filename = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, unique=True, help_text="SHA256 hash for idempotency")
    line_count = models.IntegerField(help_text="Number of rows in file")

    created_at = models.DateTimeField(auto_now_add=True)
    upload_timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ingest_raw_ingestion'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant_id']),
            models.Index(fields=['data_source_id']),
            models.Index(fields=['file_hash']),
        ]

    def __str__(self):
        return f"Ingestion {self.filename} ({self.line_count} rows)"

    @staticmethod
    def compute_hash(content_bytes):
        """Compute SHA256 hash of file content for idempotency."""
        return hashlib.sha256(content_bytes).hexdigest()


class ParsedRecord(models.Model):
    """
    A single row from a RawIngestion, parsed into a structured dict.
    Still not validated or normalized—just structured.

    Purpose: track parsing errors separately from validation errors.
    Allows analysts to see exactly what went wrong during CSV parsing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ingestion_id = models.ForeignKey(RawIngestion, on_delete=models.CASCADE, related_name='parsed_records')
    tenant_id = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='parsed_records')

    # Row number in the original file (1-indexed)
    source_row_number = models.IntegerField()

    # Raw values from CSV: {"column1": "value1", "column2": "value2", ...}
    raw_values = models.JSONField()

    # Parsing errors (if any): [{"field": "col1", "error": "unknown column"}]
    parsing_errors = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ingest_parsed_record'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ingestion_id']),
            models.Index(fields=['tenant_id']),
            models.Index(fields=['source_row_number']),
        ]
        unique_together = [['ingestion_id', 'source_row_number']]

    def __str__(self):
        return f"Row {self.source_row_number} from {self.ingestion_id}"


class NormalizedRecord(models.Model):
    """
    A ParsedRecord that has been normalized to standard schema.

    Design: Links raw CSV data → parsed structured dict → normalized standard fields.

    Stores:
    - Standard fields (facility_name, scope_1_emissions, year, etc.) as relational columns
    - Normalized values (complete mapping) as JSONB
    - Validation errors (per-field)
    - Data quality flags (warnings)

    Purpose:
    - Tracks which ParsedRecords have been normalized
    - Stores validation errors at normalization time (before EmissionsDataPoint creation)
    - Enables idempotent re-normalization (delete old, create new with updated logic)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ingestion_id = models.ForeignKey(RawIngestion, on_delete=models.CASCADE, related_name='normalized_records')
    parsed_record_id = models.ForeignKey(ParsedRecord, on_delete=models.CASCADE, related_name='normalized_record')
    tenant_id = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='normalized_records')

    # --- Standard relational fields (fast queries) ---
    facility_name = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    scope_1_emissions = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    scope_2_emissions = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    scope_3_emissions = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    reporting_year = models.IntegerField(db_index=True, null=True, blank=True)
    data_quality_score = models.IntegerField(default=0, help_text="0-100 quality score")

    # --- JSONB fields (flexible) ---
    # Complete normalized values dict: {"facility_name": "...", "scope_1_emissions": 1234.56, ...}
    normalized_values = models.JSONField(default=dict)

    # Validation errors: [{"field": "facility_name", "error": "required field missing"}]
    validation_errors = models.JSONField(default=list)

    # Data quality warnings: [{"field": "methodology", "severity": "warning", "message": "Not provided"}]
    data_quality_flags = models.JSONField(default=list)

    # Is this record valid for downstream processing?
    is_valid = models.BooleanField(default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ingest_normalized_record'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ingestion_id']),
            models.Index(fields=['tenant_id']),
            models.Index(fields=['is_valid']),
            models.Index(fields=['facility_name', 'reporting_year']),
        ]
        unique_together = [['ingestion_id', 'parsed_record_id']]

    def __str__(self):
        return f"Normalized: {self.facility_name} ({self.reporting_year}) - Valid: {self.is_valid}"
