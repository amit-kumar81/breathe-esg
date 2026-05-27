"""
Normalization logic for converting ParsedRecords to NormalizedRecords.

Chunk 1.4: Schema Definition & Normalization Rules

Process:
1. Read ParsedRecord.raw_values (dict from CSV)
2. Apply DataSource.field_mapping (CSV columns → standard fields)
3. Validate each field using validators
4. Calculate data_quality_score
5. Create NormalizedRecord with result

Design: Pure mapping (no side effects), easy to test and debug.
"""

import logging
from decimal import Decimal
from .validators import (
    validate_field_value,
    STANDARD_FIELDS,
    calculate_data_quality_score
)

logger = logging.getLogger('breathe.ingest')


def normalize_parsed_record(parsed_record, data_source):
    """
    Convert a ParsedRecord to normalized values using DataSource field mapping.

    Args:
        parsed_record: ParsedRecord object with raw_values (dict)
        data_source: DataSource object with field_mapping (dict)

    Returns:
        dict: {
            "normalized_values": {standard field dict},
            "validation_errors": [{field, error}, ...],
            "data_quality_flags": [{field, severity, message}, ...],
            "is_valid": bool,
            "data_quality_score": int
        }

    Example field_mapping in DataSource:
        {
            "Plant_Name": "facility_name",
            "Scope1_mtCO2e": "scope_1_emissions",
            "Scope2_mtCO2e": "scope_2_emissions",
            "Year": "reporting_year"
        }

    This function:
    1. Takes raw_values: {"Plant_Name": "Plant A", "Scope1_mtCO2e": "1234.56", "Year": "2023"}
    2. Maps using field_mapping: facility_name="Plant A", scope_1_emissions="1234.56", reporting_year="2023"
    3. Validates each: scope_1_emissions must be numeric, year must be 1900-2100
    4. Returns normalized values and errors
    """
    normalized_values = {}
    validation_errors = []
    data_quality_flags = []

    raw_values = parsed_record.raw_values or {}
    field_mapping = data_source.field_mapping or {}

    # Step 1: Map raw CSV columns to standard fields
    logger.info(f"Normalizing ParsedRecord {parsed_record.id} with field_mapping: {field_mapping}")

    for csv_column, standard_field in field_mapping.items():
        # Get raw value from CSV
        raw_value = raw_values.get(csv_column)

        # Check if standard_field is defined
        if standard_field not in STANDARD_FIELDS:
            error_msg = f"Unknown standard field: {standard_field} (mapped from CSV column '{csv_column}')"
            logger.warning(error_msg)
            validation_errors.append({
                "field": standard_field,
                "csv_column": csv_column,
                "error": error_msg
            })
            continue

        # Step 2: Validate using appropriate validator
        field_config = STANDARD_FIELDS[standard_field]
        is_valid, normalized_value, error_message = validate_field_value(
            standard_field,
            raw_value,
            field_config
        )

        if is_valid:
            # Convert Decimal to float so the dict is JSON-serializable for JSONB storage
            normalized_values[standard_field] = float(normalized_value) if isinstance(normalized_value, Decimal) else normalized_value
            logger.debug(f"Field {standard_field}: '{raw_value}' → {normalized_value} ✓")
        else:
            validation_errors.append({
                "field": standard_field,
                "csv_column": csv_column,
                "raw_value": raw_value,
                "error": error_message
            })
            logger.warning(f"Field {standard_field} validation failed: {error_message}")

    # Step 3: Check for unmapped CSV columns (warning, not error)
    for csv_column in raw_values.keys():
        if csv_column not in field_mapping:
            logger.debug(f"CSV column '{csv_column}' not in field_mapping (ignored)")

    # Step 4: Check for missing required fields
    for standard_field, field_config in STANDARD_FIELDS.items():
        is_required = field_config.get('required', True)
        is_present = standard_field in normalized_values

        if is_required and not is_present:
            error_msg = f"Required field '{standard_field}' not provided"
            validation_errors.append({
                "field": standard_field,
                "error": error_msg
            })
            logger.warning(error_msg)

    # Step 5: Calculate data quality score
    data_quality_score = calculate_data_quality_score(normalized_values, validation_errors)

    # Step 6: Check validity (no validation errors = valid)
    is_valid = len(validation_errors) == 0

    logger.info(
        f"Normalization complete for row {parsed_record.source_row_number}: "
        f"valid={is_valid}, score={data_quality_score}, errors={len(validation_errors)}"
    )

    return {
        "normalized_values": normalized_values,
        "validation_errors": validation_errors,
        "data_quality_flags": data_quality_flags,
        "is_valid": is_valid,
        "data_quality_score": data_quality_score
    }


def normalize_ingestion(raw_ingestion):
    """
    Normalize all ParsedRecords in an ingestion.

    Args:
        raw_ingestion: RawIngestion object

    Returns:
        dict: {
            "total_parsed": int,
            "total_normalized": int,
            "valid_count": int,
            "invalid_count": int,
            "normalization_errors": [...]
        }
    """
    from .models import ParsedRecord, NormalizedRecord

    data_source = raw_ingestion.data_source_id
    parsed_records = ParsedRecord.objects.filter(ingestion_id=raw_ingestion)

    # Auto-populate field_mapping from CSV headers if it's still empty.
    # Tries common naming conventions: Plant_Name→facility_name, Scope1_MT→scope_1_emissions, etc.
    if not data_source.field_mapping:
        import csv as csv_module, io as io_module
        csv_text = raw_ingestion.raw_csv_content
        reader = csv_module.reader(io_module.StringIO(csv_text))
        headers = next(reader, [])

        AUTO_MAP = {
            # facility
            'plant_name': 'facility_name', 'facility': 'facility_name',
            'facility_name': 'facility_name', 'site': 'facility_name',
            'location': 'facility_name', 'plant': 'facility_name',
            # scope 1
            'scope1_mt': 'scope_1_emissions', 'scope1': 'scope_1_emissions',
            'scope_1': 'scope_1_emissions', 'scope_1_emissions': 'scope_1_emissions',
            'scope1_mtco2e': 'scope_1_emissions', 'direct_emissions': 'scope_1_emissions',
            # scope 2
            'scope2_mt': 'scope_2_emissions', 'scope2': 'scope_2_emissions',
            'scope_2': 'scope_2_emissions', 'scope_2_emissions': 'scope_2_emissions',
            'scope2_mtco2e': 'scope_2_emissions', 'indirect_emissions': 'scope_2_emissions',
            # scope 3
            'scope3_mt': 'scope_3_emissions', 'scope3': 'scope_3_emissions',
            'scope_3': 'scope_3_emissions', 'scope_3_emissions': 'scope_3_emissions',
            'scope3_mtco2e': 'scope_3_emissions',
            # year
            'year': 'reporting_year', 'reporting_year': 'reporting_year',
            'report_year': 'reporting_year', 'fiscal_year': 'reporting_year',
        }

        detected = {}
        for h in headers:
            std = AUTO_MAP.get(h.lower().strip())
            if std:
                detected[h] = std

        if detected:
            data_source.field_mapping = detected
            data_source.save(update_fields=['field_mapping'])
            logger.info(f"Auto-detected field_mapping for DataSource {data_source.id}: {detected}")

    total_parsed = parsed_records.count()
    logger.info(f"Starting normalization for ingestion {raw_ingestion.id}: {total_parsed} parsed records")

    # Clear existing NormalizedRecords (idempotent)
    old_normalized = NormalizedRecord.objects.filter(ingestion_id=raw_ingestion).count()
    if old_normalized > 0:
        logger.info(f"Clearing {old_normalized} existing NormalizedRecords")
        NormalizedRecord.objects.filter(ingestion_id=raw_ingestion).delete()

    # Normalize all records, collect results, bulk_create in one query
    records_to_create = []
    valid_count = 0
    invalid_count = 0
    normalization_errors = []

    for parsed_record in parsed_records:
        try:
            result = normalize_parsed_record(parsed_record, data_source)
            records_to_create.append(NormalizedRecord(
                ingestion_id=raw_ingestion,
                parsed_record_id=parsed_record,
                tenant_id=raw_ingestion.tenant_id,
                facility_name=result['normalized_values'].get('facility_name'),
                scope_1_emissions=result['normalized_values'].get('scope_1_emissions'),
                scope_2_emissions=result['normalized_values'].get('scope_2_emissions'),
                scope_3_emissions=result['normalized_values'].get('scope_3_emissions'),
                reporting_year=result['normalized_values'].get('reporting_year'),
                data_quality_score=result['data_quality_score'],
                normalized_values=result['normalized_values'],
                validation_errors=result['validation_errors'],
                data_quality_flags=result['data_quality_flags'],
                is_valid=result['is_valid']
            ))
            if result['is_valid']:
                valid_count += 1
            else:
                invalid_count += 1
        except Exception as e:
            error_msg = f"Error normalizing row {parsed_record.source_row_number}: {str(e)}"
            normalization_errors.append({"row_number": parsed_record.source_row_number, "error": error_msg})
            logger.error(error_msg, exc_info=True)
            invalid_count += 1

    NormalizedRecord.objects.bulk_create(records_to_create, batch_size=500)
    total_normalized = len(records_to_create)

    logger.info(
        f"Normalization complete: {total_normalized} normalized, "
        f"{valid_count} valid, {invalid_count} invalid"
    )

    return {
        "total_parsed": total_parsed,
        "total_normalized": total_normalized,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "normalization_errors": normalization_errors
    }
