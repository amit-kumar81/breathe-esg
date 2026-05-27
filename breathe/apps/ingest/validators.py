"""
Field validators for emissions data normalization.

Chunk 1.4: Schema Definition & Normalization Rules

Each validator:
- Takes a raw string value from CSV
- Returns (is_valid: bool, normalized_value: any, error_message: str)
- Handles None/empty gracefully
- Logs validation errors
"""

import logging
import re
from decimal import Decimal, InvalidOperation

logger = logging.getLogger('breathe.ingest')

# Standard year range (ESG reporting typically 2010-2050)
MIN_YEAR = 1900
MAX_YEAR = 2100


def validate_facility_name(value, required=True):
    """
    Validate facility name (string, required by default).

    Returns:
        tuple: (is_valid, normalized_value, error_message)

    Examples:
        validate_facility_name("Plant A") → (True, "Plant A", None)
        validate_facility_name("  Plant B  ") → (True, "Plant B", None)  # Trimmed
        validate_facility_name("") → (False, None, "Facility name is required")
        validate_facility_name(None) → (False, None, "Facility name is required")
    """
    # Handle None and empty strings
    if value is None or value == "":
        if required:
            return False, None, "Facility name is required"
        else:
            return True, None, None

    # Convert to string and trim
    value_str = str(value).strip()

    # Check if empty after trimming
    if not value_str:
        if required:
            return False, None, "Facility name is required (only whitespace)"
        else:
            return True, None, None

    # Check length
    if len(value_str) > 255:
        return False, None, f"Facility name exceeds 255 characters (length: {len(value_str)})"

    return True, value_str, None


def validate_emissions_value(value, allow_zero=True, allow_negative=False):
    """
    Validate emissions numeric value (Decimal).

    Args:
        value: String or numeric value from CSV
        allow_zero: If False, require value > 0
        allow_negative: If True, allow negative values (credit scenarios)

    Returns:
        tuple: (is_valid, normalized_value, error_message)

    Examples:
        validate_emissions_value("1234.56") → (True, Decimal("1234.56"), None)
        validate_emissions_value("0") → (True, Decimal("0"), None) if allow_zero=True
        validate_emissions_value("abc") → (False, None, "Invalid number format")
        validate_emissions_value("-100") → (False, None, "Value must be non-negative") if allow_negative=False
    """
    # Handle None and empty strings
    if value is None or value == "":
        return False, None, "Emissions value is required"

    # Try to convert to Decimal (handles float, int, string)
    try:
        value_str = str(value).strip()
        decimal_value = Decimal(value_str)
    except (InvalidOperation, ValueError):
        return False, None, f"Invalid number format: '{value}' (must be numeric)"

    # Check for NaN or Infinity
    if decimal_value.is_nan() or decimal_value.is_infinite():
        return False, None, "Value cannot be NaN or Infinity"

    # Check bounds
    if not allow_negative and decimal_value < 0:
        return False, None, f"Emissions value must be non-negative (got: {decimal_value})"

    if not allow_zero and decimal_value == 0:
        return False, None, "Emissions value must be greater than zero"

    # Limit precision: max 15 digits total, 4 decimal places
    # (matches database DecimalField(max_digits=15, decimal_places=4))
    if len(str(abs(decimal_value.as_tuple().digits))) > 11:  # 15 - 4 = 11 integer digits
        return False, None, f"Emissions value exceeds maximum precision (got: {decimal_value})"

    return True, decimal_value, None


def validate_reporting_year(value, min_year=MIN_YEAR, max_year=MAX_YEAR):
    """
    Validate reporting year (integer).

    Args:
        value: String or numeric year from CSV
        min_year: Minimum valid year
        max_year: Maximum valid year

    Returns:
        tuple: (is_valid, normalized_value, error_message)

    Examples:
        validate_reporting_year("2023") → (True, 2023, None)
        validate_reporting_year(2023) → (True, 2023, None)
        validate_reporting_year("2000") → (False, None, "Year out of range (1900-2100)")
        validate_reporting_year("abc") → (False, None, "Invalid year format")
        validate_reporting_year("") → (False, None, "Reporting year is required")
    """
    # Handle None and empty strings
    if value is None or value == "":
        return False, None, "Reporting year is required"

    # Try to convert to int
    try:
        value_str = str(value).strip()
        year_value = int(value_str)
    except ValueError:
        return False, None, f"Invalid year format: '{value}' (must be numeric)"

    # Check range
    if year_value < min_year or year_value > max_year:
        return False, None, f"Year out of range ({min_year}-{max_year}), got {year_value}"

    return True, year_value, None


def validate_data_quality_score(value):
    """
    Validate data quality score (0-100).

    Returns:
        tuple: (is_valid, normalized_value, error_message)

    Examples:
        validate_data_quality_score("85") → (True, 85, None)
        validate_data_quality_score("") → (True, 0, None)  # Default to 0
        validate_data_quality_score("150") → (False, None, "Score must be 0-100")
    """
    # Handle None and empty strings - default to 0
    if value is None or value == "" or value == "0":
        return True, 0, None

    # Try to convert to int
    try:
        value_str = str(value).strip()
        score_value = int(value_str)
    except ValueError:
        return False, None, f"Invalid score format: '{value}' (must be numeric)"

    # Check range
    if score_value < 0 or score_value > 100:
        return False, None, f"Quality score must be 0-100, got {score_value}"

    return True, score_value, None


def validate_field_value(field_name, value, field_config):
    """
    Generic field validator dispatcher.

    Args:
        field_name: Name of field (facility_name, scope_1_emissions, etc.)
        value: Raw value from CSV
        field_config: Configuration dict with validation rules

    Returns:
        tuple: (is_valid, normalized_value, error_message)
    """
    field_type = field_config.get('type')  # 'string', 'number', 'year', 'score'
    required = field_config.get('required', True)

    if field_type == 'string':
        return validate_facility_name(value, required=required)

    elif field_type == 'number':
        allow_zero = field_config.get('allow_zero', True)
        allow_negative = field_config.get('allow_negative', False)
        return validate_emissions_value(value, allow_zero=allow_zero, allow_negative=allow_negative)

    elif field_type == 'year':
        return validate_reporting_year(value)

    elif field_type == 'score':
        return validate_data_quality_score(value)

    else:
        return False, None, f"Unknown field type: {field_type}"


# Standard field definitions for emissions data
STANDARD_FIELDS = {
    'facility_name': {
        'type': 'string',
        'required': True,
        'description': 'Name of facility/location',
        'examples': ['Plant A', 'Office Building 1']
    },
    'scope_1_emissions': {
        'type': 'number',
        'required': False,
        'allow_zero': True,
        'allow_negative': False,
        'description': 'Direct emissions (Scope 1) in mtCO2e',
        'examples': ['1234.56', '0']
    },
    'scope_2_emissions': {
        'type': 'number',
        'required': False,
        'allow_zero': True,
        'allow_negative': False,
        'description': 'Indirect emissions (Scope 2) in mtCO2e',
        'examples': ['567.89', '0']
    },
    'scope_3_emissions': {
        'type': 'number',
        'required': False,
        'allow_zero': True,
        'allow_negative': False,
        'description': 'Value chain emissions (Scope 3) in mtCO2e',
        'examples': ['2000.00', '0']
    },
    'reporting_year': {
        'type': 'year',
        'required': True,
        'min': MIN_YEAR,
        'max': MAX_YEAR,
        'description': 'Year of emissions report',
        'examples': ['2023', '2022']
    },
    'data_quality_score': {
        'type': 'score',
        'required': False,
        'description': 'Quality score 0-100',
        'examples': ['85', '75']
    }
}


def calculate_data_quality_score(normalized_values, validation_errors):
    """
    Calculate a data quality score (0-100) based on:
    - Presence of optional fields
    - Validation error count
    - Completeness

    Args:
        normalized_values: Dict of normalized values
        validation_errors: List of validation error dicts

    Returns:
        int: Score 0-100

    Scoring:
    - Start at 100
    - -10 for each validation error
    - -5 for each missing optional field (scope_2, scope_3)
    - Floor at 0
    """
    score = 100

    # Deduct for validation errors
    score -= len(validation_errors) * 10

    # Deduct for missing optional fields
    if not normalized_values.get('scope_2_emissions'):
        score -= 5
    if not normalized_values.get('scope_3_emissions'):
        score -= 5

    # Floor at 0
    return max(0, score)
