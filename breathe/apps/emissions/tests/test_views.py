"""
API integration tests for breathe/apps/emissions/views.py

Covers:
  GET /api/emissions/             — list with filtering/ordering
  GET /api/emissions/{id}/        — detail view
  GET /api/emissions/{id}/audit/  — audit trail
  GET /api/emissions/summary/     — dashboard stats with and without filters
"""

from breathe.tests.base import BaseBreatheTestCase
from breathe.apps.emissions.models import EmissionsDataPoint


class EmissionsListTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        self.p1 = self.create_emissions_point("Alpha Plant", "SCOPE_1", 1000.0, 2023)
        self.p2 = self.create_emissions_point("Alpha Plant", "SCOPE_2", 500.0, 2023)
        self.p3 = self.create_emissions_point("Beta Plant", "SCOPE_1", 2000.0, 2022)

    def test_list_returns_200(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/")
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_still_returns_data(self):
        # DRF DEFAULT_PERMISSION_CLASSES not set → defaults to AllowAny
        resp = self.client.get("/api/emissions/")
        self.assertEqual(resp.status_code, 200)

    def test_list_has_results(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/")
        self.assertGreaterEqual(resp.data["count"], 3)

    def test_filter_by_year(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/?year=2022")
        self.assertEqual(resp.status_code, 200)
        for item in resp.data["results"]:
            self.assertEqual(item["year"], 2022)

    def test_filter_by_scope(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/?scope=SCOPE_1")
        self.assertEqual(resp.status_code, 200)
        for item in resp.data["results"]:
            self.assertEqual(item["scope"], "SCOPE_1")

    def test_filter_by_facility_name(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/?facility_name=Alpha+Plant")
        self.assertEqual(resp.status_code, 200)
        for item in resp.data["results"]:
            self.assertEqual(item["facility_name"], "Alpha Plant")

    def test_order_by_year_ascending(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/?ordering=year")
        years = [r["year"] for r in resp.data["results"]]
        self.assertEqual(years, sorted(years))

    def test_order_by_emissions_value_descending(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/?ordering=-emissions_value")
        values = [float(r["emissions_value"]) for r in resp.data["results"]]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_list_items_have_expected_fields(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/")
        item = resp.data["results"][0]
        for field in ["id", "facility_name", "scope", "emissions_value", "emissions_unit", "year", "is_valid"]:
            self.assertIn(field, item)

    def test_pagination_has_count_and_next(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/")
        self.assertIn("count", resp.data)
        self.assertIn("results", resp.data)


class EmissionsDetailTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        self.point = self.create_emissions_point("Alpha Plant", "SCOPE_1", 1000.0, 2023)

    def test_retrieve_returns_200(self):
        self.auth(self.viewer)
        resp = self.client.get(f"/api/emissions/{self.point.id}/")
        self.assertEqual(resp.status_code, 200)

    def test_retrieve_returns_correct_record(self):
        self.auth(self.viewer)
        resp = self.client.get(f"/api/emissions/{self.point.id}/")
        self.assertEqual(resp.data["facility_name"], "Alpha Plant")
        self.assertAlmostEqual(float(resp.data["emissions_value"]), 1000.0, places=2)

    def test_retrieve_404_for_unknown_id(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(resp.status_code, 404)

    def test_retrieve_unauthenticated_allowed(self):
        resp = self.client.get(f"/api/emissions/{self.point.id}/")
        self.assertEqual(resp.status_code, 200)


class EmissionsAuditTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        self.point = self.create_emissions_point("Alpha Plant", "SCOPE_1", 1000.0, 2023)

    def test_audit_returns_200(self):
        self.auth(self.viewer)
        resp = self.client.get(f"/api/emissions/{self.point.id}/audit/")
        self.assertEqual(resp.status_code, 200)

    def test_audit_response_has_expected_keys(self):
        self.auth(self.viewer)
        resp = self.client.get(f"/api/emissions/{self.point.id}/audit/")
        self.assertIn("emissions_data_point_id", resp.data)
        self.assertIn("total_changes", resp.data)
        self.assertIn("audit_trail", resp.data)

    def test_audit_trail_is_list(self):
        self.auth(self.viewer)
        resp = self.client.get(f"/api/emissions/{self.point.id}/audit/")
        self.assertIsInstance(resp.data["audit_trail"], list)


class EmissionsSummaryTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        # Three plants, multiple scopes, two years
        self.create_emissions_point("Alpha", "SCOPE_1", 1000.0, 2023)
        self.create_emissions_point("Alpha", "SCOPE_2", 500.0, 2023)
        self.create_emissions_point("Beta",  "SCOPE_1", 2000.0, 2023)
        self.create_emissions_point("Beta",  "SCOPE_2", 800.0, 2022)
        self.create_emissions_point("Gamma", "SCOPE_3", 300.0, 2022)

    def test_summary_returns_200(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        self.assertEqual(resp.status_code, 200)

    def test_summary_unauthenticated_allowed(self):
        resp = self.client.get("/api/emissions/summary/")
        self.assertEqual(resp.status_code, 200)

    def test_summary_has_required_keys(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        for key in [
            "total_emissions", "facility_count", "record_count",
            "average_quality_score", "available_years", "available_facilities",
            "by_scope", "by_year",
        ]:
            self.assertIn(key, resp.data)

    def test_total_emissions_matches_sum(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        expected = 1000 + 500 + 2000 + 800 + 300
        self.assertAlmostEqual(resp.data["total_emissions"], expected, places=0)

    def test_facility_count_is_correct(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        self.assertEqual(resp.data["facility_count"], 3)

    def test_available_years_includes_all_years(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        self.assertIn(2022, resp.data["available_years"])
        self.assertIn(2023, resp.data["available_years"])

    def test_available_facilities_includes_all_facilities(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        facilities = resp.data["available_facilities"]
        self.assertIn("Alpha", facilities)
        self.assertIn("Beta", facilities)
        self.assertIn("Gamma", facilities)

    def test_by_scope_has_three_entries(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        self.assertEqual(len(resp.data["by_scope"]), 3)

    def test_by_scope_labels_are_correct(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        labels = {item["scope"] for item in resp.data["by_scope"]}
        self.assertIn("Scope 1", labels)
        self.assertIn("Scope 2", labels)
        self.assertIn("Scope 3", labels)

    def test_by_year_has_entry_for_each_year(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        years = {item["year"] for item in resp.data["by_year"]}
        self.assertIn(2022, years)
        self.assertIn(2023, years)

    def test_filter_by_year_reduces_total(self):
        self.auth(self.viewer)
        resp_all = self.client.get("/api/emissions/summary/")
        resp_2023 = self.client.get("/api/emissions/summary/?year=2023")
        self.assertLess(resp_2023.data["total_emissions"], resp_all.data["total_emissions"])

    def test_filter_by_year_does_not_reduce_available_years(self):
        """available_years always shows all years regardless of filter."""
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/?year=2023")
        self.assertIn(2022, resp.data["available_years"])

    def test_filter_by_facility_reduces_records(self):
        self.auth(self.viewer)
        resp_all = self.client.get("/api/emissions/summary/")
        resp_alpha = self.client.get("/api/emissions/summary/?facility_name=Alpha")
        self.assertLess(resp_alpha.data["record_count"], resp_all.data["record_count"])

    def test_filter_by_facility_does_not_reduce_available_facilities(self):
        """available_facilities always shows all facilities regardless of filter."""
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/?facility_name=Alpha")
        facilities = resp.data["available_facilities"]
        self.assertIn("Beta", facilities)
        self.assertIn("Gamma", facilities)

    def test_filter_by_scope_returns_only_that_scope_in_metrics(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/?scope=SCOPE_1")
        # Only Alpha SCOPE_1 (1000) and Beta SCOPE_1 (2000)
        self.assertAlmostEqual(resp.data["total_emissions"], 3000.0, places=0)

    def test_summary_with_no_data_returns_zeros(self):
        EmissionsDataPoint.objects.all().delete()
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total_emissions"], 0)
        self.assertEqual(resp.data["record_count"], 0)

    def test_average_quality_score_is_percentage(self):
        self.auth(self.viewer)
        resp = self.client.get("/api/emissions/summary/")
        score = resp.data["average_quality_score"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
