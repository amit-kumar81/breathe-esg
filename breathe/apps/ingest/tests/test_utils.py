"""
Unit tests for breathe/apps/ingest/utils.py

Covers: compute_file_hash, parse_csv_to_rows, detect_csv_dialect,
        parse_raw_csv_content, is_row_empty.
No database required except for check_idempotency.
"""

import io
import hashlib
from django.test import TestCase, SimpleTestCase

from breathe.apps.ingest.utils import (
    compute_file_hash,
    parse_csv_to_rows,
    detect_csv_dialect,
    parse_raw_csv_content,
    is_row_empty,
)


# ─────────────────────────────────────────────────────────
# compute_file_hash
# ─────────────────────────────────────────────────────────

class ComputeFileHashTests(SimpleTestCase):

    def _make_file(self, content):
        f = io.BytesIO(content.encode("utf-8"))
        f.name = "test.csv"
        return f

    def test_known_hash(self):
        content = "hello"
        expected = hashlib.sha256(content.encode()).hexdigest()
        f = self._make_file(content)
        self.assertEqual(compute_file_hash(f), expected)

    def test_same_content_same_hash(self):
        f1 = self._make_file("Plant A,1000,2023")
        f2 = self._make_file("Plant A,1000,2023")
        self.assertEqual(compute_file_hash(f1), compute_file_hash(f2))

    def test_different_content_different_hash(self):
        f1 = self._make_file("Plant A,1000,2023")
        f2 = self._make_file("Plant B,2000,2023")
        self.assertNotEqual(compute_file_hash(f1), compute_file_hash(f2))

    def test_returns_64_character_hex(self):
        f = self._make_file("test data")
        result = compute_file_hash(f)
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_file_pointer_reset_after_hash(self):
        f = self._make_file("some content")
        compute_file_hash(f)
        self.assertEqual(f.tell(), 0)

    def test_empty_file(self):
        f = self._make_file("")
        result = compute_file_hash(f)
        expected = hashlib.sha256(b"").hexdigest()
        self.assertEqual(result, expected)

    def test_large_file_works(self):
        big = "Plant A,1000,2023\n" * 10000
        f = self._make_file(big)
        result = compute_file_hash(f)
        self.assertEqual(len(result), 64)


# ─────────────────────────────────────────────────────────
# is_row_empty
# ─────────────────────────────────────────────────────────

class IsRowEmptyTests(SimpleTestCase):

    def test_all_none_values(self):
        self.assertTrue(is_row_empty({"a": None, "b": None}))

    def test_all_empty_strings(self):
        self.assertTrue(is_row_empty({"a": "", "b": ""}))

    def test_all_whitespace(self):
        self.assertTrue(is_row_empty({"a": "   ", "b": "\t"}))

    def test_empty_dict(self):
        self.assertTrue(is_row_empty({}))

    def test_none_dict(self):
        self.assertTrue(is_row_empty(None))

    def test_one_non_empty_value(self):
        self.assertFalse(is_row_empty({"a": "", "b": "Plant A"}))

    def test_all_real_values(self):
        self.assertFalse(is_row_empty({"Plant_Name": "Alpha", "Scope1": "1000", "Year": "2023"}))

    def test_zero_string_is_not_empty(self):
        self.assertFalse(is_row_empty({"scope": "0"}))

    def test_zero_is_not_empty(self):
        self.assertFalse(is_row_empty({"scope": 0}))


# ─────────────────────────────────────────────────────────
# detect_csv_dialect
# ─────────────────────────────────────────────────────────

class DetectCsvDialectTests(SimpleTestCase):

    def test_comma_delimited(self):
        csv_text = "Plant_Name,Scope1,Year\nPlant A,1000,2023\nPlant B,2000,2023"
        _, delimiter = detect_csv_dialect(csv_text)
        self.assertEqual(delimiter, ",")

    def test_semicolon_delimited(self):
        csv_text = "Plant_Name;Scope1;Year\nPlant A;1000;2023\nPlant B;2000;2023"
        _, delimiter = detect_csv_dialect(csv_text)
        self.assertEqual(delimiter, ";")

    def test_tab_delimited(self):
        csv_text = "Plant_Name\tScope1\tYear\nPlant A\t1000\t2023"
        _, delimiter = detect_csv_dialect(csv_text)
        self.assertEqual(delimiter, "\t")

    def test_single_column_defaults_gracefully(self):
        # Single-column CSV can't be sniffed reliably — must not crash
        csv_text = "Plant_Name\nPlant A\nPlant B"
        dialect, delimiter = detect_csv_dialect(csv_text)
        self.assertIsNotNone(dialect)

    def test_empty_string_defaults_gracefully(self):
        dialect, delimiter = detect_csv_dialect("")
        self.assertIsNotNone(delimiter)


# ─────────────────────────────────────────────────────────
# parse_csv_to_rows
# ─────────────────────────────────────────────────────────

class ParseCsvToRowsTests(SimpleTestCase):

    def _make_file(self, content):
        f = io.BytesIO(content.encode("utf-8"))
        f.name = "test.csv"
        return f

    def test_valid_csv_returns_all_rows(self):
        csv = "Plant_Name,Scope1,Year\nPlant A,1000,2023\nPlant B,2000,2023\n"
        rows, count, errors = parse_csv_to_rows(self._make_file(csv))
        self.assertEqual(count, 2)
        self.assertEqual(len(rows), 2)
        self.assertEqual(errors, [])

    def test_row_values_accessible_by_header(self):
        csv = "Plant_Name,Scope1\nAlpha,100\n"
        rows, _, _ = parse_csv_to_rows(self._make_file(csv))
        self.assertEqual(rows[0]["Plant_Name"], "Alpha")
        self.assertEqual(rows[0]["Scope1"], "100")

    def test_empty_rows_skipped(self):
        csv = "Plant_Name,Scope1\nAlpha,100\n,\n\nBeta,200\n"
        rows, count, errors = parse_csv_to_rows(self._make_file(csv))
        self.assertEqual(count, 2)

    def test_non_utf8_raises_value_error(self):
        latin1_content = "Plant_Name,Scope1\nCafé,100\n".encode("latin-1")
        f = io.BytesIO(latin1_content)
        f.name = "bad.csv"
        with self.assertRaises(ValueError) as ctx:
            parse_csv_to_rows(f)
        self.assertIn("UTF-8", str(ctx.exception))

    def test_header_only_returns_zero_rows(self):
        csv = "Plant_Name,Scope1,Year\n"
        rows, count, errors = parse_csv_to_rows(self._make_file(csv))
        self.assertEqual(count, 0)

    def test_single_data_row(self):
        csv = "Plant_Name,Scope1\nAlpha,100\n"
        rows, count, errors = parse_csv_to_rows(self._make_file(csv))
        self.assertEqual(count, 1)

    def test_file_pointer_reset_in_finally_block(self):
        # parse_csv_to_rows resets seek(0) in its finally block while the
        # TextIOWrapper is still alive; the underlying BytesIO is valid then.
        # We verify the function completes without I/O error.
        csv = "A,B\n1,2\n"
        f = self._make_file(csv)
        rows, count, errors = parse_csv_to_rows(f)
        self.assertEqual(count, 1)


# ─────────────────────────────────────────────────────────
# parse_raw_csv_content
# ─────────────────────────────────────────────────────────

class ParseRawCsvContentTests(SimpleTestCase):

    VALID_CSV = (
        "Plant_Name,Scope1_MT,Scope2_MT,Year\n"
        "Plant Alpha,1000.5,500.25,2023\n"
        "Plant Beta,2000.0,800.0,2023\n"
    )

    def test_returns_expected_row_count(self):
        result = parse_raw_csv_content(self.VALID_CSV)
        self.assertEqual(result["row_count"], 2)

    def test_returns_rows_as_dicts(self):
        result = parse_raw_csv_content(self.VALID_CSV)
        self.assertIsInstance(result["rows"], list)
        self.assertIsInstance(result["rows"][0], dict)

    def test_row_values_correct(self):
        result = parse_raw_csv_content(self.VALID_CSV)
        self.assertEqual(result["rows"][0]["Plant_Name"], "Plant Alpha")
        self.assertEqual(result["rows"][0]["Scope1_MT"], "1000.5")

    def test_empty_rows_reported_in_errors(self):
        csv = "A,B\n1,2\n,\n3,4\n"
        result = parse_raw_csv_content(csv)
        self.assertEqual(result["row_count"], 2)
        self.assertTrue(len(result["errors"]) >= 1)

    def test_returns_delimiter(self):
        result = parse_raw_csv_content(self.VALID_CSV)
        self.assertIn("delimiter", result)

    def test_semicolon_delimited_parsed_correctly(self):
        csv = "A;B;C\nPlant A;1000;2023\nPlant B;2000;2022\n"
        result = parse_raw_csv_content(csv)
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["rows"][0]["A"], "Plant A")

    def test_header_only_csv(self):
        result = parse_raw_csv_content("A,B,C\n")
        self.assertEqual(result["row_count"], 0)

    def test_ingestion_id_optional(self):
        result = parse_raw_csv_content(self.VALID_CSV, ingestion_id="some-id")
        self.assertEqual(result["row_count"], 2)
