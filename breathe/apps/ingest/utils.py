"""
Utility functions for ingest operations.

Handles:
- File hashing (SHA256 for idempotency)
- CSV parsing with dialect detection (to list of dicts)
- File reading with error handling
"""

import hashlib
import csv
import io
import logging

logger = logging.getLogger('breathe.ingest')


def compute_file_hash(file_obj):
    """
    Compute SHA256 hash of file content.

    Used for:
    - Idempotency (detect re-uploads of same file)
    - Integrity verification

    Args:
        file_obj: Django UploadedFile object

    Returns:
        str: SHA256 hex digest
    """
    file_obj.seek(0)  # Reset pointer to start
    hasher = hashlib.sha256()

    # Read file in chunks (memory efficient)
    while True:
        chunk = file_obj.read(8192)  # 8KB chunks
        if not chunk:
            break
        hasher.update(chunk)

    file_obj.seek(0)  # Reset for later use
    return hasher.hexdigest()


def parse_csv_to_rows(file_obj, strict=True):
    """
    Parse CSV file into list of dictionaries.

    Used in Chunk 1.2 for VALIDATION ONLY (to count rows).
    Does NOT store parsed rows—only raw_csv_content is stored.

    Args:
        file_obj: Django UploadedFile object
        strict: If True, raise error on malformed rows. If False, skip.

    Returns:
        tuple: (list of row dicts, line count, list of errors)

    Raises:
        ValueError: If file is not valid CSV
    """
    file_obj.seek(0)
    rows = []
    errors = []
    line_count = 0

    try:
        # Decode bytes to text
        text_file = io.TextIOWrapper(file_obj, encoding='utf-8')
        reader = csv.DictReader(text_file, strict=strict)

        # Process each row
        for line_num, row in enumerate(reader, start=2):  # Start at 2 (header is line 1)
            try:
                # Skip empty rows
                if not any(row.values()):
                    continue

                rows.append(dict(row))
                line_count += 1

            except Exception as e:
                error_msg = f"Row {line_num}: {str(e)}"
                errors.append(error_msg)
                if strict:
                    raise ValueError(error_msg)
                else:
                    logger.warning(f"Skipping row {line_num}: {str(e)}")
                    continue

    except UnicodeDecodeError as e:
        raise ValueError(f"File must be UTF-8 encoded: {str(e)}")
    except csv.Error as e:
        raise ValueError(f"Invalid CSV format: {str(e)}")
    finally:
        file_obj.seek(0)

    return rows, line_count, errors


def check_idempotency(file_hash, tenant_id):
    """
    Check if file has already been uploaded (based on hash).

    Used to detect duplicate uploads and return the same ingestion_id.

    Args:
        file_hash: SHA256 hash of file
        tenant_id: Tenant UUID

    Returns:
        RawIngestion or None: If file was previously uploaded, return that record.

    Note:
        File hash is unique, but we still check tenant_id for extra safety.
    """
    from .models import RawIngestion

    try:
        return RawIngestion.objects.get(file_hash=file_hash, tenant_id=tenant_id)
    except RawIngestion.DoesNotExist:
        return None


def detect_csv_dialect(csv_text):
    """
    Detect CSV dialect (delimiter, quote char, etc.) from raw CSV text.

    Tries common delimiters: comma, semicolon, tab, pipe.
    Returns the detected dialect and delimiter.

    Args:
        csv_text: Raw CSV content as string

    Returns:
        tuple: (dialect_name, delimiter)
            - dialect_name: 'excel', 'excel-tab', etc.
            - delimiter: comma, semicolon, tab, pipe

    Note:
        Defaults to comma if detection fails.
    """
    # Try to detect dialect using csv.Sniffer
    try:
        # Only sample first 8KB for detection (don't read entire file)
        sample = csv_text[:min(8192, len(csv_text))]

        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)

        delimiter = dialect.delimiter
        logger.info(f"Detected CSV dialect: delimiter='{delimiter}'")
        return dialect, delimiter

    except csv.Error as e:
        logger.warning(f"Could not detect dialect, defaulting to comma: {e}")
        return csv.excel, ','


def parse_raw_csv_content(raw_csv_text, ingestion_id=None, forced_delimiter=None):
    """
    Parse raw CSV text into list of dictionaries.

    This is called in Chunk 1.3 on-demand (NOT in Chunk 1.2).
    Uses dialect detection to handle various CSV formats.

    Args:
        raw_csv_text: Original CSV content as string
        ingestion_id: For logging purposes (optional)
        forced_delimiter: If set, skip dialect sniffing and use this delimiter (e.g. ';' for SAP)

    Returns:
        dict: {
            "rows": list of dicts,
            "row_count": int,
            "errors": list of error messages,
            "delimiter": detected delimiter
        }
    """
    rows = []
    errors = []
    delimiter_used = ','

    try:
        # Use forced delimiter (SAP always semicolon) or sniff from content
        if forced_delimiter:
            import csv as _csv
            dialect = _csv.excel
            delimiter_used = forced_delimiter
            logger.info(f"Using forced delimiter: '{delimiter_used}'")
        else:
            # Detect dialect
            dialect, delimiter_used = detect_csv_dialect(raw_csv_text)
            logger.info(f"Using delimiter: '{delimiter_used}'")

        # Parse CSV — always pass delimiter explicitly so forced_delimiter takes effect
        text_stream = io.StringIO(raw_csv_text)
        reader = csv.DictReader(text_stream, dialect=dialect, delimiter=delimiter_used)

        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")

        # Process each row
        for line_num, row in enumerate(reader, start=2):  # Start at 2 (header is line 1)
            try:
                # Skip empty rows
                if is_row_empty(row):
                    error_msg = f"Row {line_num}: Empty row (all fields are null or empty)"
                    errors.append(error_msg)
                    logger.warning(error_msg)
                    continue

                rows.append(dict(row))

            except Exception as e:
                error_msg = f"Row {line_num}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
                continue

        logger.info(f"Parsing complete: {len(rows)} rows parsed, {len(errors)} errors")

        return {
            "rows": rows,
            "row_count": len(rows),
            "errors": errors,
            "delimiter": delimiter_used
        }

    except Exception as e:
        logger.error(f"Critical error parsing CSV: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to parse CSV: {str(e)}")


def parse_raw_ingestion(raw_ingestion, source_type=None):
    """
    Parse a RawIngestion into ParsedRecords.

    Process (Chunk 1.3):
    1. Read raw_csv_content (source of truth)
    2. Parse with dialect detection (SAP always uses ';')
    3. Clear existing ParsedRecords (idempotent re-parsing)
    4. Create new ParsedRecords for each row
    5. Return summary

    Args:
        raw_ingestion: RawIngestion object (contains raw_csv_content)
        source_type: Optional source type string ('SAP', 'UTILITY', 'TRAVEL')

    Returns:
        dict: {
            "parsed_count": int,
            "parsing_errors": list,
            "empty_rows": list,
            "delimiter_detected": str
        }
    """
    from .models import ParsedRecord

    # Parse CSV from source of truth
    csv_text = raw_ingestion.raw_csv_content
    logger.info(f"Parsing RawIngestion {raw_ingestion.id}: {raw_ingestion.filename}")

    # SAP exports are always semicolon-delimited (European locale).
    forced_delimiter = ';' if source_type == 'SAP' else None
    parse_result = parse_raw_csv_content(csv_text, raw_ingestion.id, forced_delimiter=forced_delimiter)
    rows = parse_result["rows"]
    parsing_errors = parse_result["errors"]
    delimiter = parse_result["delimiter"]

    # Clear existing ParsedRecords (idempotent: re-parsing allowed)
    old_count = ParsedRecord.objects.filter(ingestion_id=raw_ingestion).count()
    if old_count > 0:
        logger.info(f"Clearing {old_count} existing ParsedRecords for ingestion {raw_ingestion.id}")
        ParsedRecord.objects.filter(ingestion_id=raw_ingestion).delete()

    # Build all ParsedRecord objects then bulk_create in one query
    records_to_create = [
        ParsedRecord(
            ingestion_id=raw_ingestion,
            tenant_id=raw_ingestion.tenant_id,
            source_row_number=row_num,
            raw_values=dict(row_data),
            parsing_errors=[]
        )
        for row_num, row_data in enumerate(rows, start=1)
    ]
    ParsedRecord.objects.bulk_create(records_to_create, batch_size=500)
    parsed_count = len(records_to_create)
    logger.info(f"Parsing complete: {parsed_count} ParsedRecords created, {len(parsing_errors)} errors")

    return {
        "parsed_count": parsed_count,
        "parsing_errors": parsing_errors,
        "delimiter_detected": delimiter
    }


def is_row_empty(row_dict):
    """
    Check if a CSV row is effectively empty (all fields are None, empty string, or whitespace).

    Args:
        row_dict: Dictionary from csv.DictReader

    Returns:
        bool: True if row is empty, False otherwise
    """
    if not row_dict:
        return True

    for value in row_dict.values():
        # Skip None and empty strings
        if value is None or value == "":
            continue
        # Check if it's just whitespace
        if isinstance(value, str) and value.strip() == "":
            continue
        # Found a non-empty value
        return False

    # All values are empty
    return True
