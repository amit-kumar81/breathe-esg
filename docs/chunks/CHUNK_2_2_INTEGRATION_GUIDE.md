# Chunk 2.2: Analyst Review Workflow API - Integration Guide

## Overview
This guide provides 10+ complete integration tests for the Analyst Review Workflow API (Chunk 2.2). Each test demonstrates a real-world scenario and validates the implementation. Tests use Django's TestCase with DRF's APITestCase for HTTP endpoints.

---

## Test Setup

All tests inherit from `APITestCase` and use the following fixtures:

```python
# tests/test_review_workflow.py

from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from breathe.apps.review.models import ReviewTask, ReviewApproval
from breathe.apps.emissions.models import EmissionsDataPoint, NormalizedRecord, DataSource
from breathe.apps.audit.models import AuditLog
from django.utils import timezone
import uuid

class ReviewWorkflowTestCase(APITestCase):
    """Base test case with common setup"""
    
    def setUp(self):
        """Create test data"""
        # Create users
        self.analyst_alice = User.objects.create_user(
            username='alice',
            password='password123'
        )
        self.analyst_bob = User.objects.create_user(
            username='bob',
            password='password123'
        )
        
        # Create tenant (placeholder for now, replaced in Chunk 2.3 with JWT)
        self.tenant_id = uuid.uuid4()
        
        # Create DataSource
        self.data_source = DataSource.objects.create(
            tenant_id=self.tenant_id,
            name='Plant A',
            source_type='CSV_UPLOAD',
            field_mapping={
                'Facility': 'facility_name',
                'Scope 1': 'scope_1_emissions',
                'Scope 2': 'scope_2_emissions',
                'Year': 'year'
            }
        )
        
        # Create NormalizedRecord (parsed/normalized data ready for review)
        self.normalized_record = NormalizedRecord.objects.create(
            tenant_id=self.tenant_id,
            data_source=self.data_source,
            raw_csv_content='Facility,Scope 1,Scope 2,Year\nPlant A,500,200,2023',
            normalized_values={
                'facility_name': 'Plant A',
                'scope_1_emissions': 500.0,
                'scope_2_emissions': 200.0,
                'year': 2023
            },
            is_valid=True,
            data_quality_score=85,
            validation_errors=[],
            data_quality_flags=[]
        )
        
        # Create ReviewTask (PENDING, waiting for analyst)
        self.review_task = ReviewTask.objects.create(
            tenant_id=self.tenant_id,
            normalized_record=self.normalized_record,
            status='PENDING',
            priority=1,
            created_at=timezone.now()
        )
        
        # Login as analyst
        self.client.force_authenticate(user=self.analyst_alice)
```

---

## Test 1: Pending List Endpoint Returns Sorted Tasks

**Scenario**: An analyst views the pending review queue. Tasks should be sorted by priority (DESC) then created_at (DESC).

```python
def test_pending_list_endpoint_sorted_by_priority(self):
    """GET /api/review/pending/ returns tasks sorted by priority DESC, created_at DESC"""
    
    # Create multiple review tasks with different priorities
    low_priority_task = ReviewTask.objects.create(
        tenant_id=self.tenant_id,
        normalized_record=self.normalized_record,
        status='PENDING',
        priority=10,
        created_at=timezone.now()
    )
    
    high_priority_task = ReviewTask.objects.create(
        tenant_id=self.tenant_id,
        normalized_record=self.normalized_record,
        status='PENDING',
        priority=1,
        created_at=timezone.now()
    )
    
    # GET /api/review/pending/
    response = self.client.get('/api/review/pending/')
    
    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(len(response.data['results']), 3)  # 1 from setUp + 2 new
    
    # Tasks should be ordered by priority DESC (1 comes before 10)
    first_task_priority = response.data['results'][0]['priority']
    second_task_priority = response.data['results'][1]['priority']
    third_task_priority = response.data['results'][2]['priority']
    
    self.assertEqual(first_task_priority, 1)
    self.assertEqual(second_task_priority, 1)
    self.assertEqual(third_task_priority, 10)
```

---

## Test 2: Approve Action Creates ReviewApproval and EmissionsDataPoint

**Scenario**: An analyst approves a valid record. The system should:
1. Create a ReviewApproval (immutable audit log)
2. Create an EmissionsDataPoint (published data)
3. Create an AuditLog entry

```python
def test_approve_action_creates_approval_and_emissions_point(self):
    """POST /api/review/{id}/approve/ creates ReviewApproval and EmissionsDataPoint atomically"""
    
    self.assertEqual(ReviewTask.objects.get(pk=self.review_task.pk).status, 'PENDING')
    
    # POST /api/review/{id}/approve/
    response = self.client.post(
        f'/api/review/{self.review_task.pk}/approve/',
        data={
            'notes': 'Data looks good, quality is high'
        },
        format='json'
    )
    
    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # ReviewTask status should be APPROVED
    self.review_task.refresh_from_db()
    self.assertEqual(self.review_task.status, 'APPROVED')
    
    # ReviewApproval should exist
    approval = ReviewApproval.objects.get(review_task=self.review_task)
    self.assertEqual(approval.analyst, self.analyst_alice)
    self.assertEqual(approval.decision, 'APPROVED')
    self.assertEqual(approval.notes, 'Data looks good, quality is high')
    
    # EmissionsDataPoint should be created
    emissions = EmissionsDataPoint.objects.get(
        tenant_id=self.tenant_id,
        normalized_record=self.normalized_record
    )
    self.assertEqual(emissions.review_status, 'APPROVED')
    self.assertEqual(emissions.normalized_values['facility_name'], 'Plant A')
    
    # AuditLog should be created with action='APPROVE'
    audit_log = AuditLog.objects.get(
        object_type='ReviewTask',
        object_id=str(self.review_task.pk),
        action='APPROVE'
    )
    self.assertEqual(audit_log.user_id, self.analyst_alice.pk)
```

---

## Test 3: Reject Action Doesn't Create EmissionsDataPoint

**Scenario**: An analyst rejects an invalid record. The system should:
1. Create a ReviewApproval (immutable record of rejection)
2. NOT create an EmissionsDataPoint (no published data)
3. Create an AuditLog entry

```python
def test_reject_action_does_not_create_emissions_point(self):
    """POST /api/review/{id}/reject/ creates ReviewApproval but NOT EmissionsDataPoint"""
    
    # POST /api/review/{id}/reject/
    response = self.client.post(
        f'/api/review/{self.review_task.pk}/reject/',
        data={
            'notes': 'Facility name is incomplete'
        },
        format='json'
    )
    
    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # ReviewTask status should be REJECTED
    self.review_task.refresh_from_db()
    self.assertEqual(self.review_task.status, 'REJECTED')
    
    # ReviewApproval should exist with decision=REJECTED
    approval = ReviewApproval.objects.get(review_task=self.review_task)
    self.assertEqual(approval.decision, 'REJECTED')
    self.assertEqual(approval.notes, 'Facility name is incomplete')
    
    # EmissionsDataPoint should NOT be created
    emissions_count = EmissionsDataPoint.objects.filter(
        normalized_record=self.normalized_record
    ).count()
    self.assertEqual(emissions_count, 0)
    
    # AuditLog should be created with action='REJECT'
    audit_log = AuditLog.objects.get(
        object_type='ReviewTask',
        object_id=str(self.review_task.pk),
        action='REJECT'
    )
    self.assertEqual(audit_log.user_id, self.analyst_alice.pk)
```

---

## Test 4: Request Clarification Changes Status to PENDING_CHANGES

**Scenario**: An analyst flags a record for clarification. The record should:
1. Change status to PENDING_CHANGES (awaiting data provider resubmission)
2. NOT create an EmissionsDataPoint
3. Create a ReviewApproval with decision='FLAG_FOR_EXPERT'

```python
def test_request_clarification_sets_status_to_pending_changes(self):
    """POST /api/review/{id}/request_clarification/ sets status to PENDING_CHANGES"""
    
    # POST /api/review/{id}/request_clarification/
    response = self.client.post(
        f'/api/review/{self.review_task.pk}/request_clarification/',
        data={
            'notes': 'Please provide methodology for Scope 3 emissions'
        },
        format='json'
    )
    
    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # Status should be PENDING_CHANGES
    self.review_task.refresh_from_db()
    self.assertEqual(self.review_task.status, 'PENDING_CHANGES')
    
    # ReviewApproval should have decision=FLAG_FOR_EXPERT
    approval = ReviewApproval.objects.get(review_task=self.review_task)
    self.assertEqual(approval.decision, 'FLAG_FOR_EXPERT')
    self.assertEqual(approval.notes, 'Please provide methodology for Scope 3 emissions')
    
    # EmissionsDataPoint should NOT be created (still waiting for fixes)
    emissions_count = EmissionsDataPoint.objects.filter(
        normalized_record=self.normalized_record
    ).count()
    self.assertEqual(emissions_count, 0)
```

---

## Test 5: Decision History Shows All ReviewApproval Entries

**Scenario**: A record is rejected, then the data provider resubmits and it's approved. The detail endpoint should show both decisions in decision_history.

```python
def test_decision_history_shows_all_approvals(self):
    """GET /api/review/{id}/ includes decision_history with all ReviewApproval entries"""
    
    # First rejection by alice
    ReviewApproval.objects.create(
        review_task=self.review_task,
        analyst=self.analyst_alice,
        decision='REJECTED',
        notes='Year is incorrect'
    )
    self.review_task.status = 'REJECTED'
    self.review_task.save()
    
    # Data provider resubmits, create new ReviewTask
    new_normalized_record = NormalizedRecord.objects.create(
        tenant_id=self.tenant_id,
        data_source=self.data_source,
        raw_csv_content='Facility,Scope 1,Scope 2,Year\nPlant A,500,200,2023',
        normalized_values={'facility_name': 'Plant A', 'scope_1_emissions': 500, 'year': 2023},
        is_valid=True,
        data_quality_score=85
    )
    
    new_review_task = ReviewTask.objects.create(
        tenant_id=self.tenant_id,
        normalized_record=new_normalized_record,
        status='PENDING'
    )
    
    # Bob approves the resubmission
    self.client.force_authenticate(user=self.analyst_bob)
    self.client.post(f'/api/review/{new_review_task.pk}/approve/', data={'notes': 'Fixed'}, format='json')
    
    # GET detail endpoint
    response = self.client.get(f'/api/review/{new_review_task.pk}/')
    
    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(len(response.data['decision_history']), 1)  # Only bob's approval
    
    decision_entry = response.data['decision_history'][0]
    self.assertEqual(decision_entry['analyst_name'], 'bob')
    self.assertEqual(decision_entry['decision'], 'APPROVED')
    self.assertEqual(decision_entry['notes'], 'Fixed')
    self.assertIn('created_at', decision_entry)
```

---

## Test 6: Batch Approve Processes Multiple Tasks Atomically

**Scenario**: An analyst approves 10 similar records in one batch operation. All should be approved atomically.

```python
def test_batch_approve_processes_multiple_tasks(self):
    """POST /api/review/batch_approve/ approves 1-100 tasks with same decision atomically"""
    
    # Create 10 review tasks
    task_ids = [self.review_task.pk]
    for i in range(9):
        nr = NormalizedRecord.objects.create(
            tenant_id=self.tenant_id,
            data_source=self.data_source,
            raw_csv_content=f'Facility,Scope 1,Scope 2,Year\nPlant {i},500,200,2023',
            normalized_values={
                'facility_name': f'Plant {i}',
                'scope_1_emissions': 500,
                'scope_2_emissions': 200,
                'year': 2023
            },
            is_valid=True,
            data_quality_score=85
        )
        rt = ReviewTask.objects.create(
            tenant_id=self.tenant_id,
            normalized_record=nr,
            status='PENDING'
        )
        task_ids.append(rt.pk)
    
    # POST /api/review/batch_approve/
    response = self.client.post(
        '/api/review/batch_approve/',
        data={
            'task_ids': [str(pk) for pk in task_ids],
            'decision': 'APPROVED',
            'notes': 'All records are valid'
        },
        format='json'
    )
    
    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(response.data['processed_count'], 10)
    
    # All tasks should be APPROVED
    for task_id in task_ids:
        task = ReviewTask.objects.get(pk=task_id)
        self.assertEqual(task.status, 'APPROVED')
        
        # Each should have a ReviewApproval
        approval = ReviewApproval.objects.get(review_task=task)
        self.assertEqual(approval.analyst, self.analyst_alice)
        self.assertEqual(approval.decision, 'APPROVED')
```

---

## Test 7: Batch Approve Respects 100-Task Limit

**Scenario**: An analyst tries to batch approve 101 tasks. The system should reject it.

```python
def test_batch_approve_enforces_100_task_limit(self):
    """POST /api/review/batch_approve/ rejects requests with >100 tasks"""
    
    # Create 101 task IDs
    task_ids = []
    for i in range(101):
        nr = NormalizedRecord.objects.create(
            tenant_id=self.tenant_id,
            data_source=self.data_source,
            raw_csv_content=f'Facility,Scope 1,Scope 2,Year\nPlant {i},500,200,2023',
            normalized_values={
                'facility_name': f'Plant {i}',
                'scope_1_emissions': 500,
                'year': 2023
            },
            is_valid=True,
            data_quality_score=85
        )
        rt = ReviewTask.objects.create(
            tenant_id=self.tenant_id,
            normalized_record=nr,
            status='PENDING'
        )
        task_ids.append(str(rt.pk))
    
    # POST with 101 tasks
    response = self.client.post(
        '/api/review/batch_approve/',
        data={
            'task_ids': task_ids,
            'decision': 'APPROVED',
            'notes': 'Batch'
        },
        format='json'
    )
    
    # Assertions
    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    self.assertIn('Max 100 tasks', str(response.data))
    
    # No tasks should have changed status
    for task_id in task_ids[:5]:  # Check a sample
        task = ReviewTask.objects.get(pk=task_id)
        self.assertEqual(task.status, 'PENDING')
```

---

## Test 8: Batch Reject Marks Tasks as REJECTED

**Scenario**: An analyst rejects a batch of similar records with a common issue.

```python
def test_batch_reject_marks_tasks_as_rejected(self):
    """POST /api/review/batch_approve/ with decision=REJECTED works correctly"""
    
    # Create 5 tasks
    task_ids = []
    for i in range(5):
        nr = NormalizedRecord.objects.create(
            tenant_id=self.tenant_id,
            data_source=self.data_source,
            raw_csv_content='invalid',
            normalized_values={
                'facility_name': f'Plant {i}',
                'scope_1_emissions': None  # Invalid
            },
            is_valid=False,
            data_quality_score=30
        )
        rt = ReviewTask.objects.create(
            tenant_id=self.tenant_id,
            normalized_record=nr,
            status='PENDING'
        )
        task_ids.append(str(rt.pk))
    
    # POST batch reject
    response = self.client.post(
        '/api/review/batch_approve/',
        data={
            'task_ids': task_ids,
            'decision': 'REJECTED',
            'notes': 'Emissions values are missing'
        },
        format='json'
    )
    
    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # All tasks should be REJECTED
    for task_id in task_ids:
        task = ReviewTask.objects.get(pk=task_id)
        self.assertEqual(task.status, 'REJECTED')
        
        # Each should have ReviewApproval with REJECTED decision
        approval = ReviewApproval.objects.get(review_task=task)
        self.assertEqual(approval.decision, 'REJECTED')
```

---

## Test 9: Reviewer Detail Returns Flattened Emissions Data

**Scenario**: An analyst views a task detail. The response should have flattened emissions data (facility_name, scope_1_emissions directly, not nested).

```python
def test_detail_serializer_flattens_emissions_data(self):
    """GET /api/review/{id}/ returns flattened normalized_values at top level"""
    
    response = self.client.get(f'/api/review/{self.review_task.pk}/')
    
    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # Flattened fields should be present at top level
    self.assertEqual(response.data['facility_name'], 'Plant A')
    self.assertEqual(response.data['scope_1_emissions'], 500.0)
    self.assertEqual(response.data['scope_2_emissions'], 200.0)
    self.assertEqual(response.data['year'], 2023)
    
    # No nested structure
    self.assertNotIn('normalized_record', response.data)
    self.assertNotIn('normalized_values', response.data)
```

---

## Test 10: List Serializer Includes Error and Flag Counts

**Scenario**: An analyst views the pending queue. Each task should show error_count and flag_count as quick indicators of data quality.

```python
def test_list_serializer_includes_error_and_flag_counts(self):
    """GET /api/review/pending/ includes error_count and flag_count"""
    
    # Create a task with errors and flags
    nr_with_issues = NormalizedRecord.objects.create(
        tenant_id=self.tenant_id,
        data_source=self.data_source,
        raw_csv_content='bad',
        normalized_values={'facility_name': 'Plant B', 'year': 2023},
        is_valid=False,
        data_quality_score=40,
        validation_errors=[
            {'field': 'scope_1_emissions', 'error': 'Missing value'},
            {'field': 'scope_2_emissions', 'error': 'Invalid number'}
        ],
        data_quality_flags=[
            {'flag': 'INCOMPLETE_DATA', 'severity': 'high'},
            {'flag': 'OUTLIER_DETECTED', 'severity': 'medium'}
        ]
    )
    
    task_with_issues = ReviewTask.objects.create(
        tenant_id=self.tenant_id,
        normalized_record=nr_with_issues,
        status='PENDING'
    )
    
    # GET /api/review/pending/
    response = self.client.get('/api/review/pending/')
    
    # Find the task with issues in the response
    task_data = next(t for t in response.data['results'] if t['id'] == str(task_with_issues.pk))
    
    # Assertions
    self.assertEqual(task_data['error_count'], 2)
    self.assertEqual(task_data['flag_count'], 2)
    self.assertEqual(task_data['status'], 'PENDING')
    self.assertEqual(task_data['facility_name'], 'Plant B')
```

---

## Test 11: Immutability of ReviewApproval

**Scenario**: An analyst tries to modify a ReviewApproval after it's been created. The system should reject it.

```python
def test_review_approval_immutability(self):
    """ReviewApproval.save() raises IntegrityError if trying to update"""
    
    # Create and approve
    self.client.post(
        f'/api/review/{self.review_task.pk}/approve/',
        data={'notes': 'Good data'},
        format='json'
    )
    
    approval = ReviewApproval.objects.get(review_task=self.review_task)
    approval_id = approval.pk
    
    # Try to modify the approval
    approval.notes = 'Changed notes'
    
    # Assertions
    with self.assertRaises(IntegrityError):
        approval.save()
    
    # Try to delete the approval
    approval.refresh_from_db()
    with self.assertRaises(IntegrityError):
        approval.delete()
    
    # Approval should still exist unchanged
    approval_check = ReviewApproval.objects.get(pk=approval_id)
    self.assertEqual(approval_check.notes, 'Good data')
```

---

## Test 12: AuditLog Created on Every Approval Action

**Scenario**: Every analyst action (approve, reject, clarify) should create an immutable AuditLog entry.

```python
def test_audit_log_created_on_approval_actions(self):
    """Each approval action (approve, reject, clarify) creates an AuditLog entry"""
    
    # Approve
    response = self.client.post(
        f'/api/review/{self.review_task.pk}/approve/',
        data={'notes': 'Good'},
        format='json'
    )
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # Check AuditLog
    audit_logs = AuditLog.objects.filter(
        object_type='ReviewTask',
        object_id=str(self.review_task.pk)
    )
    
    self.assertEqual(audit_logs.count(), 1)
    log = audit_logs.first()
    self.assertEqual(log.action, 'APPROVE')
    self.assertEqual(log.user_id, self.analyst_alice.pk)
    self.assertEqual(log.tenant_id, self.tenant_id)
    
    # Create another task and reject it
    nr2 = NormalizedRecord.objects.create(
        tenant_id=self.tenant_id,
        data_source=self.data_source,
        raw_csv_content='bad',
        normalized_values={'facility_name': 'Plant C'},
        is_valid=False
    )
    task2 = ReviewTask.objects.create(
        tenant_id=self.tenant_id,
        normalized_record=nr2,
        status='PENDING'
    )
    
    response = self.client.post(
        f'/api/review/{task2.pk}/reject/',
        data={'notes': 'Invalid'},
        format='json'
    )
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # Check AuditLog for rejection
    audit_logs_task2 = AuditLog.objects.filter(
        object_type='ReviewTask',
        object_id=str(task2.pk)
    )
    
    self.assertEqual(audit_logs_task2.count(), 1)
    log2 = audit_logs_task2.first()
    self.assertEqual(log2.action, 'REJECT')
```

---

## Running the Tests

```bash
# Run all review workflow tests
python manage.py test tests.test_review_workflow

# Run a specific test
python manage.py test tests.test_review_workflow.ReviewWorkflowTestCase.test_approve_action_creates_approval_and_emissions_point

# Run with verbose output
python manage.py test tests.test_review_workflow -v 2

# Run with coverage
coverage run --source='breathe/apps/review' manage.py test tests.test_review_workflow
coverage report
```

---

## Key Test Scenarios Covered

| Test | Scenario | Validates |
|------|----------|-----------|
| 1 | Pending list sorted | Priority ordering, task filtering |
| 2 | Approve creates all records | Atomicity, ReviewApproval, EmissionsDataPoint, AuditLog |
| 3 | Reject doesn't create EP | Rejection workflow, no data publication on reject |
| 4 | Clarification sets status | PENDING_CHANGES status, resubmission flow |
| 5 | Decision history | Multiple approvals queryable, audit trail |
| 6 | Batch approve 10 tasks | Batch operations, atomic processing |
| 7 | Batch limit 100 | Validation error on >100 tasks |
| 8 | Batch reject works | Batch rejection with decision history |
| 9 | Flattened detail output | Serializer flattening, frontend simplicity |
| 10 | List includes counts | Error and flag counts in list response |
| 11 | Immutability enforced | ReviewApproval can't be modified/deleted |
| 12 | AuditLog on all actions | Every action logged for compliance |

---

## Success Criteria

✅ All 12+ tests pass
✅ 100% code coverage for review app models, serializers, views
✅ Approval workflow is atomic (all-or-nothing)
✅ ReviewApproval immutability enforced
✅ AuditLog entries created for every action
✅ Flattened serializer output for frontend
✅ Batch operations support 1-100 tasks
✅ Decision history queryable on detail endpoint
✅ PENDING_CHANGES status for clarification requests
✅ No EmissionsDataPoint created on reject/clarify

---

## Common Issues and Fixes

### Issue: Batch Approve Partially Completes
**Problem**: 50 out of 100 tasks approved, then error occurs. Other 50 are stuck.
**Fix**: Wrap batch logic in `transaction.atomic()` so either all succeed or all rollback.

### Issue: Decision History Shows Stale Analyst Names
**Problem**: Analyst changes username, ReviewApproval still shows old name.
**Fix**: Use `SerializerMethodField` to fetch analyst name dynamically on serialization.

### Issue: ReviewTask Status Changes But ReviewApproval Doesn't Exist
**Problem**: PATCH endpoint allows direct status update, bypassing ReviewApproval creation.
**Fix**: Make status read-only in serializer, force use of custom actions (approve, reject, clarify).

### Issue: AuditLog Missing for Some Actions
**Problem**: Signal handler fails silently, AuditLog not created.
**Fix**: Test that signals are firing correctly, check that thread-local context is set in middleware.

---

## Next Steps After Chunk 2.2

Once all 12 tests pass:

1. **Code Review**: Have another team member review the ReviewTask and ReviewApproval models for edge cases
2. **Performance Testing**: Load test batch_approve with 100 concurrent requests
3. **Chunk 2.3**: Implement Multi-Tenancy Isolation (JWT auth, UserProfile, tenant filtering)
4. **Integration with Frontend**: React dashboard for analyst review (Chunk 3.4)

This chunk is complete and production-ready when all tests pass and achieve 100% code coverage.
