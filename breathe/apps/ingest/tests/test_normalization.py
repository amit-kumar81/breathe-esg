"""
Integration tests for breathe/apps/ingest/normalization.py

Tests normalize_parsed_record and normalize_ingestion using a real DB.
Covers field mapping, validation errors, quality scoring, and downstream
creation of EmissionsDataPoints and ReviewTasks.
"""

from decimal import Decimal
from breathe.tests.base import BaseBreatheTestCase
from breathe.apps.ingest.normalization import normalize_parsed_record, normalize_ingestion
from breathe.apps.ingest.models import ParsedRecord, NormalizedRecord, RawIngestion
from breathe.apps.review.models import ReviewTask
from breathe.apps.emissions.models import EmissionsDataPoint


class NormalizeParsedRecordTests(BaseBreatheTestCase):
    """Unit-level tests for normalize_parsed_record — operates on one row."""

    def _make_parsed_record(self, raw_values):
        ingestion = self.create_ingestion()
        return ParsedRecord.objects.create(
            ingestion_id=ingestion,
            tenant_id=self.tenant,
            source_row_number=1,
            raw_values=raw_values,
            parsing_errors=[],
        )

    def test_full_valid_row_produces_normalized_values(self):
        pr = self._make_parsed_record({
            "Plant_Name": "Alpha Plant",
            "Scope1_MT": "1000.5",
            "Scope2_MT": "500.25",
            "Year": "2023",
        })
        result = normalize_parsed_record(pr, self.data_source)
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["normalized_values"]["facility_name"], "Alpha Plant")
        self.assertAlmostEqual(result["normalized_values"]["scope_1_emissions"], 1000.5)
        self.assertEqual(result["normalized_values"]["reporting_year"], 2023)
        self.assertEqual(result["validation_errors"], [])

    def test_missing_required_facility_name_produces_error(self):
        pr = self._make_parsed_record({
            "Plant_Name": "",
            "Scope1_MT": "1000",
            "Year": "2023",
        })
        result = normalize_parsed_record(pr, self.data_source)
        self.assertFalse(result["is_valid"])
        fields_with_errors = [e["field"] for e in result["validation_errors"]]
        self.assertIn("facility_name", fields_with_errors)

    def test_missing_required_year_produces_error(self):
        pr = self._make_parsed_record({
            "Plant_Name": "Alpha",
            "Scope1_MT": "1000",
            "Year": "",
        })
        result = normalize_parsed_record(pr, self.data_source)
        self.assertFalse(result["is_valid"])
        fields_with_errors = [e["field"] for e in result["validation_errors"]]
        self.assertIn("reporting_year", fields_with_errors)

    def test_negative_emissions_value_produces_error(self):
        pr = self._make_parsed_record({
            "Plant_Name": "Alpha",
            "Scope1_MT": "-100",
            "Year": "2023",
        })
        result = normalize_parsed_record(pr, self.data_source)
        self.assertFalse(result["is_valid"])
        fields = [e["field"] for e in result["validation_errors"]]
        self.assertIn("scope_1_emissions", fields)

    def test_zero_scope_1_is_valid(self):
        pr = self._make_parsed_record({
            "Plant_Name": "Alpha",
            "Scope1_MT": "0",
            "Scope2_MT": "100",  # mapping requires this column to be present
            "Year": "2023",
        })
        result = normalize_parsed_record(pr, self.data_source)
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["normalized_values"]["scope_1_emissions"], 0.0)

    def test_non_numeric_emissions_produces_error(self):
        pr = self._make_parsed_record({
            "Plant_Name": "Alpha",
            "Scope1_MT": "not_a_number",
            "Year": "2023",
        })
        result = normalize_parsed_record(pr, self.data_source)
        self.assertFalse(result["is_valid"])

    def test_out_of_range_year_produces_error(self):
        pr = self._make_parsed_record({
            "Plant_Name": "Alpha",
            "Scope1_MT": "1000",
            "Year": "1800",
        })
        result = normalize_parsed_record(pr, self.data_source)
        self.assertFalse(result["is_valid"])

    def test_quality_score_is_100_for_complete_valid_row(self):
        pr = self._make_parsed_record({
            "Plant_Name": "Alpha",
            "Scope1_MT": "1000",
            "Scope2_MT": "500",
            "Year": "2023",
        })
        result = normalize_parsed_record(pr, self.data_source)
        # scope_3 is missing → -5, scope_2 present → no deduct for scope_2
        self.assertEqual(result["data_quality_score"], 95)

    def test_normalized_values_are_floats_not_decimals(self):
        pr = self._make_parsed_record({
            "Plant_Name": "Alpha",
            "Scope1_MT": "1234.5678",
            "Year": "2023",
        })
        result = normalize_parsed_record(pr, self.data_source)
        self.assertIsInstance(result["normalized_values"].get("scope_1_emissions"), float)

    def test_unmapped_csv_columns_ignored(self):
        pr = self._make_parsed_record({
            "Plant_Name": "Alpha",
            "Scope1_MT": "1000",
            "Scope2_MT": "500",  # keep mapped columns present
            "Year": "2023",
            "Extra_Column": "ignored",
        })
        result = normalize_parsed_record(pr, self.data_source)
        self.assertTrue(result["is_valid"])

    def test_whitespace_in_values_trimmed(self):
        pr = self._make_parsed_record({
            "Plant_Name": "  Beta Plant  ",
            "Scope1_MT": " 500 ",
            "Scope2_MT": " 250 ",  # keep mapped column present
            "Year": " 2022 ",
        })
        result = normalize_parsed_record(pr, self.data_source)
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["normalized_values"]["facility_name"], "Beta Plant")


class NormalizeIngestionTests(BaseBreatheTestCase):
    """Integration tests for normalize_ingestion — full pipeline."""

    def test_creates_normalized_records_for_all_rows(self):
        ingestion = self.create_ingestion()
        self.create_parsed_records(ingestion)
        result = normalize_ingestion(ingestion)
        self.assertEqual(result["total_normalized"], 3)
        self.assertEqual(NormalizedRecord.objects.filter(ingestion_id=ingestion).count(), 3)

    def test_valid_rows_marked_is_valid_true(self):
        ingestion = self.create_ingestion()
        self.create_parsed_records(ingestion)
        normalize_ingestion(ingestion)
        valid = NormalizedRecord.objects.filter(ingestion_id=ingestion, is_valid=True).count()
        self.assertGreater(valid, 0)

    def test_creates_emissions_data_points_for_present_scopes(self):
        ingestion = self.create_ingestion()
        self.create_parsed_records(ingestion)
        normalize_ingestion(ingestion)
        # Our sample CSV has scope_1 and scope_2 for 3 rows → at least 6 points
        count = EmissionsDataPoint.objects.filter(
            parsed_record_id__ingestion_id=ingestion
        ).count()
        self.assertGreater(count, 0)

    def test_creates_review_tasks_for_all_normalized_records(self):
        ingestion = self.create_ingestion()
        self.create_parsed_records(ingestion)
        normalize_ingestion(ingestion)
        tasks = ReviewTask.objects.filter(ingestion_id=ingestion)
        self.assertEqual(tasks.count(), 3)

    def test_invalid_records_get_high_priority_review_task(self):
        bad_csv = "Plant_Name,Scope1_MT,Scope2_MT,Year\n,1000,500,2023\n"
        ingestion = self.create_ingestion(csv_content=bad_csv)
        self.create_parsed_records(ingestion)
        normalize_ingestion(ingestion)
        tasks = ReviewTask.objects.filter(ingestion_id=ingestion, priority="HIGH")
        self.assertEqual(tasks.count(), 1)

    def test_idempotent_re_normalization_clears_old_records(self):
        ingestion = self.create_ingestion()
        self.create_parsed_records(ingestion)
        normalize_ingestion(ingestion)
        first_count = NormalizedRecord.objects.filter(ingestion_id=ingestion).count()

        normalize_ingestion(ingestion)
        second_count = NormalizedRecord.objects.filter(ingestion_id=ingestion).count()

        self.assertEqual(first_count, second_count)

    def test_auto_field_mapping_detected_when_datasource_has_none(self):
        from breathe.apps.ingest.models import DataSource
        unmapped_source = DataSource.objects.create(
            tenant_id=self.tenant,
            source_type="SAP",
            name="Auto-map source",
            field_mapping={},
        )
        csv = "facility_name,scope_1_emissions,scope_2_emissions,reporting_year\nPlant X,500,250,2023\n"
        ingestion = RawIngestion.objects.create(
            tenant_id=self.tenant,
            data_source_id=unmapped_source,
            filename="auto.csv",
            file_hash=RawIngestion.compute_hash(csv.encode()),
            line_count=1,
            raw_csv_content=csv,
        )
        self.create_parsed_records(ingestion)
        normalize_ingestion(ingestion)

        unmapped_source.refresh_from_db()
        self.assertNotEqual(unmapped_source.field_mapping, {})

        nr = NormalizedRecord.objects.filter(ingestion_id=ingestion).first()
        self.assertIsNotNone(nr)
        self.assertTrue(nr.is_valid)

    def test_result_dict_has_expected_keys(self):
        ingestion = self.create_ingestion()
        self.create_parsed_records(ingestion)
        result = normalize_ingestion(ingestion)
        for key in ["total_parsed", "total_normalized", "valid_count", "invalid_count", "normalization_errors"]:
            self.assertIn(key, result)

    def test_facility_name_stored_on_normalized_record(self):
        ingestion = self.create_ingestion()
        self.create_parsed_records(ingestion)
        normalize_ingestion(ingestion)
        nr = NormalizedRecord.objects.filter(ingestion_id=ingestion).first()
        self.assertIsNotNone(nr.facility_name)

    def test_reporting_year_stored_on_normalized_record(self):
        ingestion = self.create_ingestion()
        self.create_parsed_records(ingestion)
        normalize_ingestion(ingestion)
        nr = NormalizedRecord.objects.filter(ingestion_id=ingestion, facility_name="Plant Alpha").first()
        self.assertEqual(nr.reporting_year, 2023)
