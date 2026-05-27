"""
Unit tests for breathe/apps/ingest/validators.py

Tests every validator function with normal, boundary, and error inputs.
No database required — all pure functions.
"""

from decimal import Decimal
from django.test import SimpleTestCase

from breathe.apps.ingest.validators import (
    validate_facility_name,
    validate_emissions_value,
    validate_reporting_year,
    validate_data_quality_score,
    validate_field_value,
    calculate_data_quality_score,
    STANDARD_FIELDS,
)


# ─────────────────────────────────────────────────────────
# validate_facility_name
# ─────────────────────────────────────────────────────────

class ValidateFacilityNameTests(SimpleTestCase):

    def test_valid_name(self):
        ok, val, err = validate_facility_name("Plant Alpha")
        self.assertTrue(ok)
        self.assertEqual(val, "Plant Alpha")
        self.assertIsNone(err)

    def test_leading_trailing_whitespace_trimmed(self):
        ok, val, err = validate_facility_name("  Plant Beta  ")
        self.assertTrue(ok)
        self.assertEqual(val, "Plant Beta")

    def test_none_required(self):
        ok, val, err = validate_facility_name(None)
        self.assertFalse(ok)
        self.assertIsNone(val)
        self.assertIn("required", err)

    def test_empty_string_required(self):
        ok, val, err = validate_facility_name("")
        self.assertFalse(ok)
        self.assertIn("required", err)

    def test_whitespace_only_required(self):
        ok, val, err = validate_facility_name("   ")
        self.assertFalse(ok)
        self.assertIn("required", err)

    def test_none_optional(self):
        ok, val, err = validate_facility_name(None, required=False)
        self.assertTrue(ok)
        self.assertIsNone(val)
        self.assertIsNone(err)

    def test_empty_optional(self):
        ok, val, err = validate_facility_name("", required=False)
        self.assertTrue(ok)
        self.assertIsNone(val)

    def test_exactly_255_characters(self):
        name = "A" * 255
        ok, val, err = validate_facility_name(name)
        self.assertTrue(ok)
        self.assertEqual(val, name)

    def test_256_characters_fails(self):
        name = "A" * 256
        ok, val, err = validate_facility_name(name)
        self.assertFalse(ok)
        self.assertIn("255", err)

    def test_numeric_value_converted_to_string(self):
        ok, val, err = validate_facility_name(42)
        self.assertTrue(ok)
        self.assertEqual(val, "42")

    def test_special_characters_allowed(self):
        ok, val, err = validate_facility_name("Plant #1 (Alpha) – India")
        self.assertTrue(ok)

    def test_single_character(self):
        ok, val, err = validate_facility_name("X")
        self.assertTrue(ok)
        self.assertEqual(val, "X")


# ─────────────────────────────────────────────────────────
# validate_emissions_value
# ─────────────────────────────────────────────────────────

class ValidateEmissionsValueTests(SimpleTestCase):

    def test_valid_decimal_string(self):
        ok, val, err = validate_emissions_value("1234.56")
        self.assertTrue(ok)
        self.assertEqual(val, Decimal("1234.56"))
        self.assertIsNone(err)

    def test_valid_integer_string(self):
        ok, val, err = validate_emissions_value("1000")
        self.assertTrue(ok)
        self.assertEqual(val, Decimal("1000"))

    def test_zero_allowed_by_default(self):
        ok, val, err = validate_emissions_value("0")
        self.assertTrue(ok)
        self.assertEqual(val, Decimal("0"))

    def test_zero_disallowed_when_configured(self):
        ok, val, err = validate_emissions_value("0", allow_zero=False)
        self.assertFalse(ok)
        self.assertIn("greater than zero", err)

    def test_negative_disallowed_by_default(self):
        ok, val, err = validate_emissions_value("-100")
        self.assertFalse(ok)
        self.assertIn("non-negative", err)

    def test_negative_allowed_when_configured(self):
        ok, val, err = validate_emissions_value("-100", allow_negative=True)
        self.assertTrue(ok)
        self.assertEqual(val, Decimal("-100"))

    def test_none_returns_error(self):
        ok, val, err = validate_emissions_value(None)
        self.assertFalse(ok)
        self.assertIn("required", err)

    def test_empty_string_returns_error(self):
        ok, val, err = validate_emissions_value("")
        self.assertFalse(ok)
        self.assertIn("required", err)

    def test_non_numeric_string(self):
        ok, val, err = validate_emissions_value("abc")
        self.assertFalse(ok)
        self.assertIn("Invalid number format", err)

    def test_mixed_string(self):
        ok, val, err = validate_emissions_value("123abc")
        self.assertFalse(ok)

    def test_value_too_large(self):
        ok, val, err = validate_emissions_value("100000000001")
        self.assertFalse(ok)
        self.assertIn("maximum precision", err)

    def test_large_valid_value(self):
        ok, val, err = validate_emissions_value("99999999999.9999")
        self.assertTrue(ok)

    def test_float_input(self):
        ok, val, err = validate_emissions_value(1234.56)
        self.assertTrue(ok)
        self.assertAlmostEqual(float(val), 1234.56, places=2)

    def test_whitespace_stripped(self):
        ok, val, err = validate_emissions_value("  500.0  ")
        self.assertTrue(ok)
        self.assertEqual(val, Decimal("500.0"))

    def test_scientific_notation(self):
        ok, val, err = validate_emissions_value("1E+3")
        self.assertTrue(ok)
        self.assertEqual(val, Decimal("1E+3"))


# ─────────────────────────────────────────────────────────
# validate_reporting_year
# ─────────────────────────────────────────────────────────

class ValidateReportingYearTests(SimpleTestCase):

    def test_valid_year_string(self):
        ok, val, err = validate_reporting_year("2023")
        self.assertTrue(ok)
        self.assertEqual(val, 2023)
        self.assertIsNone(err)

    def test_valid_year_int(self):
        ok, val, err = validate_reporting_year(2022)
        self.assertTrue(ok)
        self.assertEqual(val, 2022)

    def test_none_returns_error(self):
        ok, val, err = validate_reporting_year(None)
        self.assertFalse(ok)
        self.assertIn("required", err)

    def test_empty_string_returns_error(self):
        ok, val, err = validate_reporting_year("")
        self.assertFalse(ok)
        self.assertIn("required", err)

    def test_non_numeric_string(self):
        ok, val, err = validate_reporting_year("twenty-twenty-three")
        self.assertFalse(ok)
        self.assertIn("Invalid year format", err)

    def test_year_below_minimum(self):
        ok, val, err = validate_reporting_year("1899")
        self.assertFalse(ok)
        self.assertIn("out of range", err)

    def test_year_above_maximum(self):
        ok, val, err = validate_reporting_year("2101")
        self.assertFalse(ok)
        self.assertIn("out of range", err)

    def test_boundary_minimum(self):
        ok, val, err = validate_reporting_year("1900")
        self.assertTrue(ok)
        self.assertEqual(val, 1900)

    def test_boundary_maximum(self):
        ok, val, err = validate_reporting_year("2100")
        self.assertTrue(ok)
        self.assertEqual(val, 2100)

    def test_float_string_rejected(self):
        ok, val, err = validate_reporting_year("2023.5")
        self.assertFalse(ok)

    def test_whitespace_stripped(self):
        ok, val, err = validate_reporting_year("  2023  ")
        self.assertTrue(ok)
        self.assertEqual(val, 2023)

    def test_zero_is_out_of_range(self):
        ok, val, err = validate_reporting_year("0")
        self.assertFalse(ok)

    def test_negative_year_rejected(self):
        ok, val, err = validate_reporting_year("-1")
        self.assertFalse(ok)


# ─────────────────────────────────────────────────────────
# validate_data_quality_score
# ─────────────────────────────────────────────────────────

class ValidateDataQualityScoreTests(SimpleTestCase):

    def test_valid_score(self):
        ok, val, err = validate_data_quality_score("85")
        self.assertTrue(ok)
        self.assertEqual(val, 85)
        self.assertIsNone(err)

    def test_zero_score_string(self):
        ok, val, err = validate_data_quality_score("0")
        self.assertTrue(ok)
        self.assertEqual(val, 0)

    def test_none_defaults_to_zero(self):
        ok, val, err = validate_data_quality_score(None)
        self.assertTrue(ok)
        self.assertEqual(val, 0)

    def test_empty_defaults_to_zero(self):
        ok, val, err = validate_data_quality_score("")
        self.assertTrue(ok)
        self.assertEqual(val, 0)

    def test_100_is_valid(self):
        ok, val, err = validate_data_quality_score("100")
        self.assertTrue(ok)
        self.assertEqual(val, 100)

    def test_above_100_fails(self):
        ok, val, err = validate_data_quality_score("101")
        self.assertFalse(ok)
        self.assertIn("0-100", err)

    def test_negative_fails(self):
        ok, val, err = validate_data_quality_score("-1")
        self.assertFalse(ok)
        self.assertIn("0-100", err)

    def test_non_numeric_fails(self):
        ok, val, err = validate_data_quality_score("great")
        self.assertFalse(ok)
        self.assertIn("Invalid score format", err)

    def test_float_string_rejected(self):
        ok, val, err = validate_data_quality_score("85.5")
        self.assertFalse(ok)


# ─────────────────────────────────────────────────────────
# validate_field_value (dispatcher)
# ─────────────────────────────────────────────────────────

class ValidateFieldValueTests(SimpleTestCase):

    def test_string_field_dispatch(self):
        config = {"type": "string", "required": True}
        ok, val, err = validate_field_value("facility_name", "Plant A", config)
        self.assertTrue(ok)
        self.assertEqual(val, "Plant A")

    def test_number_field_dispatch(self):
        config = {"type": "number", "allow_zero": True, "allow_negative": False}
        ok, val, err = validate_field_value("scope_1_emissions", "500.5", config)
        self.assertTrue(ok)
        self.assertEqual(val, Decimal("500.5"))

    def test_year_field_dispatch(self):
        config = {"type": "year"}
        ok, val, err = validate_field_value("reporting_year", "2023", config)
        self.assertTrue(ok)
        self.assertEqual(val, 2023)

    def test_score_field_dispatch(self):
        config = {"type": "score"}
        ok, val, err = validate_field_value("data_quality_score", "75", config)
        self.assertTrue(ok)
        self.assertEqual(val, 75)

    def test_unknown_type_returns_error(self):
        config = {"type": "unknown_type"}
        ok, val, err = validate_field_value("some_field", "value", config)
        self.assertFalse(ok)
        self.assertIn("Unknown field type", err)


# ─────────────────────────────────────────────────────────
# calculate_data_quality_score
# ─────────────────────────────────────────────────────────

class CalculateDataQualityScoreTests(SimpleTestCase):

    def test_perfect_score_all_fields_no_errors(self):
        values = {
            "facility_name": "Plant A",
            "scope_1_emissions": 1000,
            "scope_2_emissions": 500,
            "scope_3_emissions": 200,
            "reporting_year": 2023,
        }
        score = calculate_data_quality_score(values, [])
        self.assertEqual(score, 100)

    def test_missing_scope_2_deducts_5(self):
        values = {"facility_name": "Plant A", "scope_1_emissions": 1000, "reporting_year": 2023}
        score = calculate_data_quality_score(values, [])
        self.assertEqual(score, 90)  # -5 scope_2, -5 scope_3

    def test_missing_scope_3_deducts_5(self):
        values = {
            "facility_name": "Plant A",
            "scope_1_emissions": 1000,
            "scope_2_emissions": 500,
            "reporting_year": 2023,
        }
        score = calculate_data_quality_score(values, [])
        self.assertEqual(score, 95)

    def test_one_validation_error_deducts_10(self):
        # scope_2 and scope_3 are present so no field deductions; 1 error → -10
        values = {"facility_name": "Plant A", "scope_2_emissions": 500, "scope_3_emissions": 200}
        errors = [{"field": "reporting_year", "error": "required"}]
        score = calculate_data_quality_score(values, errors)
        self.assertEqual(score, 90)  # 100 - 10 (one error), scope_2 and scope_3 present

    def test_multiple_errors_floored_at_zero(self):
        errors = [{"field": f"field_{i}", "error": "bad"} for i in range(15)]
        score = calculate_data_quality_score({}, errors)
        self.assertEqual(score, 0)

    def test_empty_scope_2_zero_treated_as_missing(self):
        # 0 is falsy — calculate_data_quality_score deducts for it
        values = {"scope_2_emissions": 0, "scope_3_emissions": 100}
        score = calculate_data_quality_score(values, [])
        self.assertEqual(score, 95)  # -5 for scope_2=0


# ─────────────────────────────────────────────────────────
# STANDARD_FIELDS completeness
# ─────────────────────────────────────────────────────────

class StandardFieldsTests(SimpleTestCase):

    def test_required_fields_present(self):
        self.assertIn("facility_name", STANDARD_FIELDS)
        self.assertIn("reporting_year", STANDARD_FIELDS)

    def test_optional_emissions_fields_present(self):
        for field in ["scope_1_emissions", "scope_2_emissions", "scope_3_emissions"]:
            self.assertIn(field, STANDARD_FIELDS)

    def test_facility_name_is_required(self):
        self.assertTrue(STANDARD_FIELDS["facility_name"].get("required"))

    def test_reporting_year_is_required(self):
        self.assertTrue(STANDARD_FIELDS["reporting_year"].get("required"))

    def test_scope_emissions_are_optional(self):
        for field in ["scope_1_emissions", "scope_2_emissions", "scope_3_emissions"]:
            self.assertFalse(STANDARD_FIELDS[field].get("required", False))

    def test_emissions_do_not_allow_negative(self):
        for field in ["scope_1_emissions", "scope_2_emissions", "scope_3_emissions"]:
            self.assertFalse(STANDARD_FIELDS[field].get("allow_negative", False))
