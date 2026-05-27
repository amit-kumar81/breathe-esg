"""
API integration tests for breathe/apps/review/views.py

Covers:
  GET  /api/review/              — list with status filter
  GET  /api/review/{id}/         — detail with decision history
  GET  /api/review/pending/      — pending-only convenience endpoint
  POST /api/review/{id}/approve/ — approve a task
  POST /api/review/{id}/reject/  — reject a task
  POST /api/review/{id}/request_clarification/
  POST /api/review/batch_approve/
"""

from breathe.tests.base import BaseBreatheTestCase
from breathe.apps.review.models import ReviewTask, ReviewApproval


class ReviewTaskListTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        ingestion = self.create_ingestion()
        self.create_normalized_records(ingestion)

    def test_list_returns_200(self):
        self.auth(self.analyst)
        resp = self.client.get("/api/review/")
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_allowed(self):
        resp = self.client.get("/api/review/")
        self.assertEqual(resp.status_code, 200)

    def test_list_contains_results_key(self):
        self.auth(self.analyst)
        resp = self.client.get("/api/review/")
        self.assertIn("results", resp.data)

    def test_filter_by_pending_status(self):
        self.auth(self.admin)
        resp = self.client.get("/api/review/?status=PENDING")
        self.assertEqual(resp.status_code, 200)
        for task in resp.data["results"]:
            self.assertEqual(task["status"], "PENDING")

    def test_filter_by_priority(self):
        self.auth(self.admin)
        resp = self.client.get("/api/review/?priority=LOW")
        self.assertEqual(resp.status_code, 200)
        for task in resp.data["results"]:
            self.assertEqual(task["priority"], "LOW")

    def test_list_task_has_facility_name(self):
        self.auth(self.analyst)
        resp = self.client.get("/api/review/")
        if resp.data["results"]:
            task = resp.data["results"][0]
            self.assertIn("facility_name", task)

    def test_list_task_has_scope_emissions(self):
        self.auth(self.analyst)
        resp = self.client.get("/api/review/")
        if resp.data["results"]:
            task = resp.data["results"][0]
            self.assertIn("scope_1_emissions", task)
            self.assertIn("scope_2_emissions", task)

    def test_list_task_has_quality_score(self):
        self.auth(self.analyst)
        resp = self.client.get("/api/review/")
        if resp.data["results"]:
            task = resp.data["results"][0]
            self.assertIn("data_quality_score", task)

    def test_list_task_has_reporting_year(self):
        self.auth(self.analyst)
        resp = self.client.get("/api/review/")
        if resp.data["results"]:
            task = resp.data["results"][0]
            self.assertIn("reporting_year", task)
            self.assertIsNotNone(task["reporting_year"])


class ReviewTaskPendingEndpointTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        ingestion = self.create_ingestion()
        self.create_normalized_records(ingestion)

    def test_pending_returns_only_pending_tasks(self):
        self.auth(self.analyst)
        resp = self.client.get("/api/review/pending/")
        self.assertEqual(resp.status_code, 200)
        for task in resp.data["results"]:
            self.assertEqual(task["status"], "PENDING")

    def test_pending_unauthenticated_allowed(self):
        resp = self.client.get("/api/review/pending/")
        self.assertEqual(resp.status_code, 200)


class ReviewTaskDetailTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        self.ingestion = self.create_ingestion()
        self.create_normalized_records(self.ingestion)
        self.task = ReviewTask.objects.filter(ingestion_id=self.ingestion).first()

    def test_retrieve_returns_200(self):
        self.auth(self.analyst)
        resp = self.client.get(f"/api/review/{self.task.id}/")
        self.assertEqual(resp.status_code, 200)

    def test_retrieve_includes_decision_history(self):
        self.auth(self.analyst)
        resp = self.client.get(f"/api/review/{self.task.id}/")
        self.assertIn("decision_history", resp.data)

    def test_retrieve_includes_validation_errors(self):
        self.auth(self.analyst)
        resp = self.client.get(f"/api/review/{self.task.id}/")
        self.assertIn("validation_errors", resp.data)

    def test_retrieve_404_for_unknown_task(self):
        self.auth(self.analyst)
        resp = self.client.get("/api/review/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(resp.status_code, 404)

    def test_retrieve_includes_approved_by_name_field(self):
        self.auth(self.analyst)
        resp = self.client.get(f"/api/review/{self.task.id}/")
        self.assertIn("approved_by_name", resp.data)
        self.assertIn("rejected_by_name", resp.data)


class ApproveTaskTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        self.ingestion = self.create_ingestion()
        self.create_normalized_records(self.ingestion)
        self.task = ReviewTask.objects.filter(ingestion_id=self.ingestion).first()

    def test_approve_returns_200(self):
        self.auth(self.analyst)
        resp = self.client.post(f"/api/review/{self.task.id}/approve/", {}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_approve_sets_task_status_to_approved(self):
        self.auth(self.analyst)
        self.client.post(f"/api/review/{self.task.id}/approve/", {}, format="json")
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "APPROVED")

    def test_approve_sets_approved_by_to_current_user(self):
        self.auth(self.analyst)
        self.client.post(f"/api/review/{self.task.id}/approve/", {}, format="json")
        self.task.refresh_from_db()
        self.assertEqual(self.task.approved_by, self.analyst)

    def test_approve_sets_approved_at_timestamp(self):
        self.auth(self.analyst)
        self.client.post(f"/api/review/{self.task.id}/approve/", {}, format="json")
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.approved_at)

    def test_approve_with_notes_stores_notes(self):
        self.auth(self.analyst)
        self.client.post(
            f"/api/review/{self.task.id}/approve/",
            {"notes": "Looks correct, approved."},
            format="json",
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.analyst_notes, "Looks correct, approved.")

    def test_approve_without_notes_succeeds(self):
        self.auth(self.analyst)
        resp = self.client.post(f"/api/review/{self.task.id}/approve/", {}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_approve_creates_review_approval_record(self):
        self.auth(self.analyst)
        before = ReviewApproval.objects.count()
        self.client.post(f"/api/review/{self.task.id}/approve/", {}, format="json")
        self.assertEqual(ReviewApproval.objects.count(), before + 1)

    def test_approve_review_approval_has_correct_decision(self):
        self.auth(self.analyst)
        self.client.post(f"/api/review/{self.task.id}/approve/", {}, format="json")
        approval = ReviewApproval.objects.filter(review_task_id=self.task).first()
        self.assertEqual(approval.decision, "APPROVED")

    def test_approve_404_for_unknown_task(self):
        self.auth(self.analyst)
        resp = self.client.post(
            "/api/review/00000000-0000-0000-0000-000000000000/approve/",
            {}, format="json"
        )
        self.assertEqual(resp.status_code, 404)

    def test_approve_unauthenticated_crashes_assigning_anonymous_user(self):
        # AnonymousUser cannot be assigned to approved_by (ForeignKey to User) → 500
        self.client.raise_request_exception = False
        resp = self.client.post(f"/api/review/{self.task.id}/approve/", {}, format="json")
        self.assertEqual(resp.status_code, 500)

    def test_approve_response_has_status_field(self):
        self.auth(self.analyst)
        resp = self.client.post(f"/api/review/{self.task.id}/approve/", {}, format="json")
        self.assertIn("status", resp.data)
        self.assertEqual(resp.data["status"], "approved")

    def test_viewer_can_also_approve_no_role_restriction_in_view(self):
        # The view itself does NOT enforce role — frontend does.
        # Verify the API does not reject a VIEWER for approve.
        self.auth(self.viewer)
        resp = self.client.post(f"/api/review/{self.task.id}/approve/", {}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_notes_max_length_1000_respected(self):
        self.auth(self.analyst)
        long_notes = "x" * 1001
        resp = self.client.post(
            f"/api/review/{self.task.id}/approve/",
            {"notes": long_notes},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)


class RejectTaskTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        self.ingestion = self.create_ingestion()
        self.create_normalized_records(self.ingestion)
        self.task = ReviewTask.objects.filter(ingestion_id=self.ingestion).first()

    def test_reject_returns_200(self):
        self.auth(self.analyst)
        resp = self.client.post(
            f"/api/review/{self.task.id}/reject/",
            {"notes": "Missing scope 3 data."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_reject_sets_task_status_to_rejected(self):
        self.auth(self.analyst)
        self.client.post(
            f"/api/review/{self.task.id}/reject/",
            {"notes": "Data error"},
            format="json",
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "REJECTED")

    def test_reject_sets_rejected_by_to_current_user(self):
        self.auth(self.analyst)
        self.client.post(f"/api/review/{self.task.id}/reject/", {}, format="json")
        self.task.refresh_from_db()
        self.assertEqual(self.task.rejected_by, self.analyst)

    def test_reject_sets_rejected_at_timestamp(self):
        self.auth(self.analyst)
        self.client.post(f"/api/review/{self.task.id}/reject/", {}, format="json")
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.rejected_at)

    def test_reject_without_notes_succeeds(self):
        self.auth(self.analyst)
        resp = self.client.post(f"/api/review/{self.task.id}/reject/", {}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_reject_creates_review_approval_with_rejected_decision(self):
        self.auth(self.analyst)
        self.client.post(f"/api/review/{self.task.id}/reject/", {}, format="json")
        approval = ReviewApproval.objects.filter(review_task_id=self.task).first()
        self.assertIsNotNone(approval)
        self.assertEqual(approval.decision, "REJECTED")

    def test_reject_404_for_unknown_task(self):
        self.auth(self.analyst)
        resp = self.client.post(
            "/api/review/00000000-0000-0000-0000-000000000000/reject/",
            {}, format="json"
        )
        self.assertEqual(resp.status_code, 404)

    def test_reject_response_has_status_rejected(self):
        self.auth(self.analyst)
        resp = self.client.post(f"/api/review/{self.task.id}/reject/", {}, format="json")
        self.assertEqual(resp.data["status"], "rejected")


class RequestClarificationTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        self.ingestion = self.create_ingestion()
        self.create_normalized_records(self.ingestion)
        self.task = ReviewTask.objects.filter(ingestion_id=self.ingestion).first()

    def test_request_clarification_returns_200(self):
        self.auth(self.analyst)
        resp = self.client.post(
            f"/api/review/{self.task.id}/request_clarification/",
            {"notes": "Please provide scope 3 data."},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_status_set_to_pending_changes(self):
        self.auth(self.analyst)
        self.client.post(
            f"/api/review/{self.task.id}/request_clarification/",
            {"notes": "Needs work"},
            format="json",
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "PENDING_CHANGES")

    def test_creates_flag_for_expert_approval(self):
        self.auth(self.analyst)
        self.client.post(
            f"/api/review/{self.task.id}/request_clarification/",
            {"notes": "Check this"},
            format="json",
        )
        approval = ReviewApproval.objects.filter(review_task_id=self.task).first()
        self.assertEqual(approval.decision, "FLAG_FOR_EXPERT")


class BatchApproveTests(BaseBreatheTestCase):

    def setUp(self):
        super().setUp()
        self.ingestion = self.create_ingestion()
        self.create_normalized_records(self.ingestion)
        self.tasks = list(ReviewTask.objects.filter(ingestion_id=self.ingestion))

    def test_batch_approve_returns_200(self):
        self.auth(self.admin)
        task_ids = [str(t.id) for t in self.tasks[:2]]
        resp = self.client.post(
            "/api/review/batch_approve/",
            {"task_ids": task_ids, "decision": "APPROVED"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_batch_approve_updates_all_tasks(self):
        self.auth(self.admin)
        task_ids = [str(t.id) for t in self.tasks]
        self.client.post(
            "/api/review/batch_approve/",
            {"task_ids": task_ids, "decision": "APPROVED"},
            format="json",
        )
        for task in self.tasks:
            task.refresh_from_db()
            self.assertEqual(task.status, "APPROVED")

    def test_batch_reject_updates_all_tasks(self):
        self.auth(self.admin)
        task_ids = [str(t.id) for t in self.tasks]
        self.client.post(
            "/api/review/batch_approve/",
            {"task_ids": task_ids, "decision": "REJECTED", "notes": "Bulk reject"},
            format="json",
        )
        for task in self.tasks:
            task.refresh_from_db()
            self.assertEqual(task.status, "REJECTED")

    def test_batch_missing_task_ids_returns_400(self):
        self.auth(self.admin)
        resp = self.client.post(
            "/api/review/batch_approve/",
            {"decision": "APPROVED"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_batch_empty_task_ids_returns_400(self):
        self.auth(self.admin)
        resp = self.client.post(
            "/api/review/batch_approve/",
            {"task_ids": [], "decision": "APPROVED"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_batch_invalid_decision_returns_400(self):
        self.auth(self.admin)
        resp = self.client.post(
            "/api/review/batch_approve/",
            {"task_ids": [str(self.tasks[0].id)], "decision": "MAYBE"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_batch_response_includes_approved_count(self):
        self.auth(self.admin)
        task_ids = [str(t.id) for t in self.tasks]
        resp = self.client.post(
            "/api/review/batch_approve/",
            {"task_ids": task_ids, "decision": "APPROVED"},
            format="json",
        )
        self.assertIn("approved_count", resp.data)
        self.assertEqual(resp.data["approved_count"], len(self.tasks))

    def test_batch_unauthenticated_returns_400_for_invalid_ids(self):
        # No auth guard; UUID validation rejects "fake"
        resp = self.client.post(
            "/api/review/batch_approve/",
            {"task_ids": ["not-a-uuid"], "decision": "APPROVED"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
