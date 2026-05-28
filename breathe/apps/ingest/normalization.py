"""
Normalization pipeline: converts ParsedRecords into NormalizedRecords.

Each source type (SAP, UTILITY, TRAVEL) has its own normalization function
because the raw data shapes are fundamentally different:

  SAP:     German column names, semicolon-delimited, CO2e values are pre-calculated
           inside SAP's Environmental Compliance module. Date in DD.MM.YYYY.
           → Direct field-map + date parse.

  UTILITY: Portal CSV, billing periods that don't align with calendar months,
           raw kWh. NO CO2e column. Must multiply by grid emission factor.
           → kWh × 0.000716 mtCO2e/kWh (CEA India 2022-23 baseline).

  TRAVEL:  Concur-style expense report, one row per expense line item.
           Expense type drives which emission factor to use:
             FLIGHT:     ICAO factor by distance bracket (short vs long haul)
             HOTEL:      DEFRA 2023 per-night factor
             CAR_RENTAL/TAXI: DEFRA 2023 average car per-km factor
           → Activity quantity × factor → scope_3_emissions.
"""

import logging
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger('breathe.ingest')

# ---------------------------------------------------------------------------
# Emission factors (all in mtCO2e per unit)
# ---------------------------------------------------------------------------

# India Central Electricity Authority (CEA) 2022-23 CO2 baseline (Scope 2)
INDIA_GRID_FACTOR_MT_PER_KWH = Decimal('0.000716')

# ICAO Carbon Footprint methodology (Scope 3, passenger air travel, economy class)
# Includes radiative forcing multiplier of 1.9 per ICAO 2023 guidance.
FLIGHT_SHORT_HAUL_MT_PER_KM = Decimal('0.000000255')   # < 1500 km
FLIGHT_LONG_HAUL_MT_PER_KM  = Decimal('0.000000195')   # >= 1500 km

# DEFRA 2023 conversion factors (Scope 3)
HOTEL_MT_PER_NIGHT    = Decimal('0.0000313')    # average hotel, all room types
CAR_MT_PER_KM         = Decimal('0.000000171')  # average rental/taxi car


def _parse_sap_date(date_str):
    """
    Parse SAP date string to reporting year integer.
    Handles DD.MM.YYYY (German locale) and YYYYMMDD (SAP internal).
    Returns None if unparseable.
    """
    if not date_str or str(date_str).strip() == '':
        return None
    s = str(date_str).strip()
    for fmt in ('%d.%m.%Y', '%Y%m%d', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).year
        except ValueError:
            continue
    return None


def _parse_date_year(date_str):
    """
    Parse a date string (various formats) and return the year.
    Used for utility billing periods and travel transaction dates.
    """
    if not date_str or str(date_str).strip() == '':
        return None
    s = str(date_str).strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d.%m.%Y', '%m/%d/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).year
        except ValueError:
            continue
    return None


def _to_decimal(value, field_name='value'):
    """
    Safely convert a string to Decimal. Returns None on failure.
    Handles European decimal commas if they slip through (e.g. "1.234,56").
    """
    if value is None or str(value).strip() == '':
        return None
    s = str(value).strip().replace(' ', '')
    # European format: 1.234,56 → 1234.56
    if ',' in s and '.' in s and s.index(',') > s.index('.'):
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s and '.' not in s:
        s = s.replace(',', '.')
    try:
        return Decimal(s)
    except Exception:
        logger.warning(f"Could not convert {field_name}='{value}' to Decimal")
        return None


# ---------------------------------------------------------------------------
# SAP normalization
# ---------------------------------------------------------------------------

def normalize_sap_record(raw_values, field_mapping):
    """
    Map German SAP column names to standard fields.
    Values are already CO2e (from SAP Environmental Compliance).
    Handles DD.MM.YYYY dates and tCO2e unit (≡ mtCO2e, 1 tonne = 1 metric ton).

    Expected CSV columns (via DataSource.field_mapping):
      Werksname      → facility_name
      Buchungsjahr   → reporting_year  (4-digit year)
      Bericht_Datum  → sap_report_date (stored in extra_values, not STANDARD_FIELDS)
      Scope1_tCO2e   → scope_1_emissions
      Scope2_tCO2e   → scope_2_emissions
      Scope3_tCO2e   → scope_3_emissions
    """
    normalized = {}
    errors = []
    extra = {}

    for csv_col, std_field in field_mapping.items():
        raw = raw_values.get(csv_col)

        if std_field == 'facility_name':
            v = str(raw).strip() if raw else None
            if not v:
                errors.append({'field': 'facility_name', 'error': 'Required field missing'})
            else:
                normalized['facility_name'] = v

        elif std_field == 'reporting_year':
            # Buchungsjahr is typically a 4-digit year string like "2023"
            # Bericht_Datum would be DD.MM.YYYY — try year parse from either
            year = None
            if raw:
                s = str(raw).strip()
                if len(s) == 4 and s.isdigit():
                    year = int(s)
                else:
                    year = _parse_sap_date(s)
            if year is None:
                errors.append({'field': 'reporting_year', 'error': f'Cannot parse year from: {raw}'})
            else:
                normalized['reporting_year'] = year

        elif std_field in ('scope_1_emissions', 'scope_2_emissions', 'scope_3_emissions'):
            v = _to_decimal(raw, std_field)
            if v is None:
                if raw is not None and str(raw).strip() != '':
                    errors.append({'field': std_field, 'error': f'Invalid number: {raw}'})
                # Scope 2/3 may legitimately be absent for some facilities
            elif v < 0:
                errors.append({'field': std_field, 'error': f'Negative emissions value: {v}'})
            else:
                normalized[std_field] = float(v)  # JSON-serializable

        else:
            # Unknown or extra field — store in extra dict (goes into normalized_values JSONB)
            extra[std_field] = raw

    # Also store the raw plant code if present (not in field_mapping but useful for audit)
    if 'Werks' in raw_values:
        extra['sap_plant_code'] = raw_values['Werks']
    if 'Bericht_Datum' in raw_values:
        extra['sap_report_date'] = raw_values['Bericht_Datum']

    normalized.update(extra)
    return normalized, errors


# ---------------------------------------------------------------------------
# Utility normalization
# ---------------------------------------------------------------------------

def normalize_utility_record(raw_values, field_mapping):
    """
    Convert utility portal CSV row into mtCO2e (Scope 2).

    Key decisions:
    - Emission factor: India CEA 2022-23 grid baseline = 0.716 kgCO2e/kWh = 0.000716 mtCO2e/kWh
    - Billing period: dates extracted for the year attribution. If a billing period
      spans a year boundary (e.g. Dec 15 – Jan 14), we attribute the full period
      to the year of Billing_Start. This is consistent with GHG Protocol guidance
      that recommends using the period the consumption occurred, not when billed.
    - Raw kWh is stored in normalized_values for auditability.

    Expected field_mapping:
      Site_Name     → facility_name
      Billing_Start → billing_period_start
      Usage_kWh     → usage_kwh
    """
    normalized = {}
    errors = []

    for csv_col, std_field in field_mapping.items():
        raw = raw_values.get(csv_col)

        if std_field == 'facility_name':
            v = str(raw).strip() if raw else None
            if not v:
                errors.append({'field': 'facility_name', 'error': 'Required field missing'})
            else:
                normalized['facility_name'] = v

        elif std_field == 'billing_period_start':
            normalized['billing_period_start'] = str(raw).strip() if raw else None
            year = _parse_date_year(raw)
            if year:
                normalized['reporting_year'] = year
            else:
                errors.append({'field': 'reporting_year', 'error': f'Cannot parse year from Billing_Start: {raw}'})

        elif std_field == 'billing_period_end':
            normalized['billing_period_end'] = str(raw).strip() if raw else None

        elif std_field == 'usage_kwh':
            kwh = _to_decimal(raw, 'usage_kwh')
            if kwh is None or kwh < 0:
                errors.append({'field': 'usage_kwh', 'error': f'Invalid kWh value: {raw}'})
            else:
                normalized['usage_kwh'] = float(kwh)
                # Convert to Scope 2 emissions (electricity is always Scope 2)
                scope2 = kwh * INDIA_GRID_FACTOR_MT_PER_KWH
                normalized['scope_2_emissions'] = float(scope2.quantize(Decimal('0.000001')))
                normalized['emission_factor_used'] = float(INDIA_GRID_FACTOR_MT_PER_KWH)
                normalized['emission_factor_source'] = 'CEA India 2022-23'

        else:
            # Extra columns (rate code, charges, meter_id, account_number, peak demand)
            normalized[std_field] = str(raw).strip() if raw else None

    # Pass-through useful metadata columns even if not in field_mapping
    for col in ('Account_Number', 'Meter_ID', 'Rate_Code', 'Peak_Demand_kW', 'Charges_INR'):
        if col in raw_values and col not in field_mapping:
            normalized[col.lower()] = raw_values[col]

    return normalized, errors


# ---------------------------------------------------------------------------
# Travel normalization
# ---------------------------------------------------------------------------

def normalize_travel_record(raw_values, field_mapping):
    """
    Convert a Concur expense line item into mtCO2e (Scope 3).

    Expense type determines the emission factor:
      FLIGHT:              ICAO factor × distance_km (short or long haul threshold: 1500 km)
      HOTEL:               DEFRA 2023 × hotel_nights
      CAR_RENTAL / TAXI:   DEFRA 2023 average car × distance_km

    If distance_km is missing for a FLIGHT, we flag it as a data quality issue
    (we cannot calculate without distance). In production you'd look up IATA
    airport coordinates to derive great-circle distance.

    All travel emissions are Scope 3 (Category 6: Business Travel).
    facility_name is always 'Business Travel' since there is no physical facility.
    """
    normalized = {}
    errors = []

    # First pass: collect all raw values via field_mapping
    mapped = {}
    for csv_col, std_field in field_mapping.items():
        mapped[std_field] = raw_values.get(csv_col)

    # Also pull unmapped columns directly (Concur exports have many columns)
    expense_type = (
        mapped.get('expense_type')
        or raw_values.get('Expense_Type')
        or raw_values.get('expense_type', '')
    )
    expense_type = str(expense_type).strip().upper() if expense_type else ''

    origin = raw_values.get('Origin_IATA') or mapped.get('origin_iata', '')
    destination = raw_values.get('Destination_IATA') or mapped.get('destination_iata', '')
    distance_km = _to_decimal(
        raw_values.get('Distance_km') or mapped.get('distance_km'),
        'distance_km'
    )
    hotel_nights = _to_decimal(
        raw_values.get('Hotel_Nights') or mapped.get('hotel_nights'),
        'hotel_nights'
    )

    normalized['facility_name'] = 'Business Travel'

    # reporting_year from transaction date
    date_raw = mapped.get('transaction_date') or raw_values.get('Transaction_Date')
    year = _parse_date_year(date_raw)
    if year:
        normalized['reporting_year'] = year
    else:
        errors.append({'field': 'reporting_year', 'error': f'Cannot parse year from Transaction_Date: {date_raw}'})

    # Store travel metadata
    normalized['expense_type'] = expense_type
    normalized['origin_iata'] = str(origin).strip() if origin else None
    normalized['destination_iata'] = str(destination).strip() if destination else None
    normalized['employee_id'] = raw_values.get('Employee_ID', '')
    normalized['business_purpose'] = raw_values.get('Business_Purpose', '')

    # Calculate Scope 3 emissions based on expense type
    scope3 = None

    if expense_type == 'FLIGHT':
        if distance_km is None or distance_km <= 0:
            errors.append({
                'field': 'distance_km',
                'error': (
                    f'Flight from {origin} to {destination}: Distance_km is required '
                    f'to calculate emissions. In production, derive from IATA airport coordinates.'
                )
            })
        else:
            factor = (
                FLIGHT_SHORT_HAUL_MT_PER_KM
                if distance_km < 1500
                else FLIGHT_LONG_HAUL_MT_PER_KM
            )
            scope3 = distance_km * factor
            normalized['emission_factor_used'] = float(factor)
            normalized['emission_factor_source'] = 'ICAO 2023 (economy class, incl. radiative forcing)'
            normalized['distance_km'] = float(distance_km)

    elif expense_type == 'HOTEL':
        if hotel_nights is None or hotel_nights <= 0:
            errors.append({'field': 'hotel_nights', 'error': 'Hotel_Nights required for HOTEL expense type'})
        else:
            scope3 = hotel_nights * HOTEL_MT_PER_NIGHT
            normalized['emission_factor_used'] = float(HOTEL_MT_PER_NIGHT)
            normalized['emission_factor_source'] = 'DEFRA 2023 (average hotel per night)'
            normalized['hotel_nights'] = float(hotel_nights)

    elif expense_type in ('CAR_RENTAL', 'TAXI', 'GROUND'):
        if distance_km is None or distance_km <= 0:
            errors.append({'field': 'distance_km', 'error': 'Distance_km required for ground transport'})
        else:
            scope3 = distance_km * CAR_MT_PER_KM
            normalized['emission_factor_used'] = float(CAR_MT_PER_KM)
            normalized['emission_factor_source'] = 'DEFRA 2023 (average car)'
            normalized['distance_km'] = float(distance_km)

    else:
        errors.append({'field': 'expense_type', 'error': f'Unrecognised expense type: {expense_type}. Expected FLIGHT, HOTEL, CAR_RENTAL, or TAXI.'})

    if scope3 is not None:
        normalized['scope_3_emissions'] = float(scope3.quantize(Decimal('0.000001')))

    return normalized, errors


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def normalize_parsed_record(parsed_record, data_source):
    """
    Dispatch to the correct source-type normalizer based on DataSource.source_type.
    Returns a dict ready to populate NormalizedRecord fields.
    """
    source_type = data_source.source_type  # 'SAP', 'UTILITY', 'TRAVEL'
    raw_values = parsed_record.raw_values or {}
    field_mapping = data_source.field_mapping or {}

    if source_type == 'UTILITY':
        normalized_values, validation_errors = normalize_utility_record(raw_values, field_mapping)
    elif source_type == 'TRAVEL':
        normalized_values, validation_errors = normalize_travel_record(raw_values, field_mapping)
    else:
        # SAP (default)
        normalized_values, validation_errors = normalize_sap_record(raw_values, field_mapping)

    data_quality_flags = []
    is_valid = len(validation_errors) == 0
    data_quality_score = _calculate_quality_score(normalized_values, validation_errors, source_type)

    logger.info(
        f"Normalized row {parsed_record.source_row_number} [{source_type}]: "
        f"valid={is_valid}, score={data_quality_score}, errors={len(validation_errors)}"
    )

    return {
        'normalized_values': normalized_values,
        'validation_errors': validation_errors,
        'data_quality_flags': data_quality_flags,
        'is_valid': is_valid,
        'data_quality_score': data_quality_score,
    }


def _calculate_quality_score(normalized_values, validation_errors, source_type):
    score = 100
    score -= len(validation_errors) * 15

    if source_type == 'SAP':
        if not normalized_values.get('scope_2_emissions'):
            score -= 5
        if not normalized_values.get('scope_3_emissions'):
            score -= 5
    elif source_type == 'UTILITY':
        if not normalized_values.get('usage_kwh'):
            score -= 20
        if not normalized_values.get('billing_period_start'):
            score -= 10
    elif source_type == 'TRAVEL':
        if not normalized_values.get('expense_type'):
            score -= 15
        if normalized_values.get('expense_type') == 'FLIGHT' and not normalized_values.get('distance_km'):
            score -= 20

    return max(0, score)


# ---------------------------------------------------------------------------
# Bulk normalization (called from views_workflow.py)
# ---------------------------------------------------------------------------

def normalize_ingestion(raw_ingestion):
    """
    Normalize all ParsedRecords in a RawIngestion.
    Creates NormalizedRecord, EmissionsDataPoint, and ReviewTask for each row.
    Idempotent: re-running deletes previous results first.
    """
    from .models import ParsedRecord, NormalizedRecord
    from breathe.apps.emissions.models import EmissionsDataPoint
    from breathe.apps.review.models import ReviewTask

    data_source = raw_ingestion.data_source_id
    source_type = data_source.source_type

    # Auto-detect field mapping from CSV headers if not yet configured.
    # Each source type has its own known column conventions.
    if not data_source.field_mapping:
        import csv as csv_module, io as io_module
        reader = csv_module.reader(io_module.StringIO(raw_ingestion.raw_csv_content))
        headers = next(reader, [])

        AUTO_MAP = {
            'SAP': {
                'werksname': 'facility_name',
                'buchungsjahr': 'reporting_year',
                'bericht_datum': 'sap_report_date',
                'scope1_tco2e': 'scope_1_emissions',
                'scope2_tco2e': 'scope_2_emissions',
                'scope3_tco2e': 'scope_3_emissions',
                # Also handle non-German fallback headers
                'plant_name': 'facility_name',
                'year': 'reporting_year',
            },
            'UTILITY': {
                'site_name': 'facility_name',
                'billing_start': 'billing_period_start',
                'billing_end': 'billing_period_end',
                'usage_kwh': 'usage_kwh',
                'account_number': 'account_number',
                'meter_id': 'meter_id',
                'rate_code': 'rate_code',
                'peak_demand_kw': 'peak_demand_kw',
                'charges_inr': 'charges_inr',
            },
            'TRAVEL': {
                'employee_id': 'employee_id',
                'transaction_date': 'transaction_date',
                'expense_type': 'expense_type',
                'origin_iata': 'origin_iata',
                'destination_iata': 'destination_iata',
                'distance_km': 'distance_km',
                'hotel_nights': 'hotel_nights',
                'vendor': 'vendor',
                'business_purpose': 'business_purpose',
            },
        }

        source_map = AUTO_MAP.get(source_type, AUTO_MAP['SAP'])
        detected = {}
        for h in headers:
            std = source_map.get(h.lower().strip())
            if std:
                detected[h] = std

        if detected:
            data_source.field_mapping = detected
            data_source.save(update_fields=['field_mapping'])
            logger.info(f"Auto-detected field_mapping for {source_type} DataSource {data_source.id}: {detected}")

    parsed_records = ParsedRecord.objects.filter(ingestion_id=raw_ingestion)
    total_parsed = parsed_records.count()
    logger.info(f"Starting normalization: ingestion={raw_ingestion.id}, source_type={source_type}, rows={total_parsed}")

    # Idempotent: clear previous results
    NormalizedRecord.objects.filter(ingestion_id=raw_ingestion).delete()
    EmissionsDataPoint.objects.filter(parsed_record_id__ingestion_id=raw_ingestion).delete()
    # Also remove orphaned EDPs whose parsed_record_id was set to NULL by a prior re-parse
    EmissionsDataPoint.objects.filter(
        parsed_record_id__isnull=True,
        data_source_id=raw_ingestion.data_source_id,
        tenant_id=raw_ingestion.tenant_id,
    ).delete()
    ReviewTask.objects.filter(ingestion_id=raw_ingestion).delete()

    nr_to_create = []
    valid_count = 0
    invalid_count = 0
    normalization_errors = []

    for pr in parsed_records:
        try:
            result = normalize_parsed_record(pr, data_source)
            nv = result['normalized_values']
            nr_to_create.append(NormalizedRecord(
                ingestion_id=raw_ingestion,
                parsed_record_id=pr,
                tenant_id=raw_ingestion.tenant_id,
                facility_name=nv.get('facility_name'),
                scope_1_emissions=nv.get('scope_1_emissions'),
                scope_2_emissions=nv.get('scope_2_emissions'),
                scope_3_emissions=nv.get('scope_3_emissions'),
                reporting_year=nv.get('reporting_year'),
                data_quality_score=result['data_quality_score'],
                normalized_values=nv,
                validation_errors=result['validation_errors'],
                data_quality_flags=result['data_quality_flags'],
                is_valid=result['is_valid'],
            ))
            if result['is_valid']:
                valid_count += 1
            else:
                invalid_count += 1
        except Exception as e:
            msg = f"Error normalizing row {pr.source_row_number}: {e}"
            normalization_errors.append({'row_number': pr.source_row_number, 'error': msg})
            logger.error(msg, exc_info=True)
            invalid_count += 1

    NormalizedRecord.objects.bulk_create(nr_to_create, batch_size=500)

    # Create EmissionsDataPoints (one per scope per NormalizedRecord where value is present)
    scope_fields = [
        ('scope_1_emissions', 'SCOPE_1'),
        ('scope_2_emissions', 'SCOPE_2'),
        ('scope_3_emissions', 'SCOPE_3'),
    ]
    emission_points = []
    for nr in NormalizedRecord.objects.filter(ingestion_id=raw_ingestion):
        for field_name, scope_code in scope_fields:
            value = getattr(nr, field_name)
            if value is not None:
                emission_points.append(EmissionsDataPoint(
                    tenant_id=raw_ingestion.tenant_id,
                    parsed_record_id=nr.parsed_record_id,
                    data_source_id=raw_ingestion.data_source_id,
                    facility_name=nr.facility_name or '',
                    scope=scope_code,
                    emissions_value=value,
                    emissions_unit='mtCO2e',
                    year=nr.reporting_year or 0,
                    methodology=nr.normalized_values.get('emission_factor_source', ''),
                    is_valid=nr.is_valid,
                    normalized_values=nr.normalized_values,
                    validation_errors=nr.validation_errors,
                    data_quality_flags=nr.data_quality_flags,
                ))
    EmissionsDataPoint.objects.bulk_create(emission_points, batch_size=500)

    # Create ReviewTasks for analyst sign-off
    review_tasks = []
    for nr in NormalizedRecord.objects.filter(ingestion_id=raw_ingestion):
        if not nr.is_valid:
            priority = 'HIGH'
            reason_codes = ['validation_error']
        elif nr.data_quality_score < 70:
            priority = 'MEDIUM'
            reason_codes = ['low_quality']
        else:
            priority = 'LOW'
            reason_codes = ['routine_review']

        review_tasks.append(ReviewTask(
            ingestion_id=raw_ingestion,
            normalized_record_id=nr,
            tenant_id=raw_ingestion.tenant_id,
            status='PENDING',
            priority=priority,
            reason_codes=reason_codes,
        ))
    ReviewTask.objects.bulk_create(review_tasks, batch_size=500)

    logger.info(
        f"Normalization complete [{source_type}]: total={len(nr_to_create)}, "
        f"valid={valid_count}, invalid={invalid_count}, "
        f"emissions_points={len(emission_points)}, review_tasks={len(review_tasks)}"
    )

    return {
        'total_parsed': total_parsed,
        'total_normalized': len(nr_to_create),
        'valid_count': valid_count,
        'invalid_count': invalid_count,
        'normalization_errors': normalization_errors,
    }
