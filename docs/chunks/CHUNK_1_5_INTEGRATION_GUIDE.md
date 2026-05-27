# Chunk 1.5: Analyst Review & Approval Workflow — Integration Guide

## Test Setup

### Prerequisites

From previous chunks, ensure you have:
- Completed migrations for Chunks 1.1-1.4
- At least one Tenant
- One DataSource with field_mapping
- One ingestion with ParsedRecords and NormalizedRecords

If not, follow CHUNK_1_2_INTEGRATION_GUIDE.md through CHUNK_1_4_INTEGRATION_GUIDE.md.

### Django Migration

```bash
cd D:\BreatheESG Assignment
docker-compose exec backend python manage.py makemigrations review
docker-compose exec backend python manage.py migrate review
```

Creates:
- `review_review_task` table
- `review_review_approval` table
- Indexes on status, priority, decision

### Create Test User (Analyst)

```bash
docker-compose exec backend python manage.py shell
```

```python
from django.contrib.auth.models import User
from breathe.apps.tenants.models import Tenant

tenant = Tenant.objects.first()

# Create analyst user
analyst = User.objects.create_user(
    username='alice',
    email='alice@company.com',
    password='password123'
)

# In Chunk 2.3, we'll add UserProfile.tenant_id
# For now, just create the user
print(f"Analyst created: {analyst.email}")

exit()
```

---

## Test Cases

### Test 1: Auto-Create ReviewTask for Invalid Record

**Setup:**
Use CSV with missing facility_name from CHUNK_1_4_INTEGRATION_GUIDE.md (test 3):
```csv
Plant_Name,Scope1_mtCO2e,Year
,1000,2023
Plant B,abc,2023
Plant C,2000,1850
Plant D,2000,2023
```

Expected: 1 valid, 3 invalid NormalizedRecords.

**Steps:**

1. Upload, Parse, Normalize (from Chunk 1.4):
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_invalid.csv" \
  -F "data_source_id=<DS_ID>"
# Save INGEST_ID

curl -X POST http://localhost:8000/api/ingest/$INGEST_ID/parse/
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID/normalize/
```

2. Check NormalizedRecords:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord
from breathe.apps.review.models import ReviewTask

records = NormalizedRecord.objects.all()
print(f"Total NormalizedRecords: {records.count()}")  # 4

valid_count = records.filter(is_valid=True).count()
invalid_count = records.filter(is_valid=False).count()
print(f"Valid: {valid_count}, Invalid: {invalid_count}")  # 1 valid, 3 invalid

# For each invalid record, ReviewTask should exist
for record in records.filter(is_valid=False):
    task = ReviewTask.objects.get(normalized_record_id=record)
    print(f"Row {record.parsed_record_id.source_row_number}: "
          f"Task {task.id} ({task.status})")

exit()
```

**Expected Output:**
```
Total NormalizedRecords: 4
Valid: 1, Invalid: 3
Row 1: Task <uuid> (PENDING)
Row 2: Task <uuid> (PENDING)
Row 3: Task <uuid> (PENDING)
```

---

### Test 2: Auto-Approve Valid Records

**Setup:**
Use CSV with all valid data from CHUNK_1_4_INTEGRATION_GUIDE.md (test 1).

**Steps:**

1. Upload, Parse, Normalize:
```bash
# (same workflow as test 1)
```

2. Check ReviewTasks:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord
from breathe.apps.review.models import ReviewTask
from breathe.apps.emissions.models import EmissionsDataPoint

# Valid records should NOT create ReviewTask
valid_records = NormalizedRecord.objects.filter(is_valid=True, data_quality_score__gte=80)
print(f"Valid records: {valid_records.count()}")  # Should be > 0

review_tasks = ReviewTask.objects.filter(
    normalized_record_id__in=valid_records
)
print(f"Review tasks for valid: {review_tasks.count()}")  # Should be 0

# Valid records should auto-create EmissionsDataPoint
emissions = EmissionsDataPoint.objects.filter(
    parsed_record_id__in=[r.parsed_record_id for r in valid_records]
)
print(f"EmissionsDataPoints created: {emissions.count()}")
# Should equal valid_records.count()

exit()
```

**Expected Output:**
```
Valid records: 3
Review tasks for valid: 0
EmissionsDataPoints created: 3
```

---

### Test 3: List Pending ReviewTasks (Dashboard)

**Setup:**
From Test 1, should have 3 pending ReviewTasks.

**Steps:**

```bash
curl -X GET http://localhost:8000/api/review/pending/ \
  -H "Authorization: Bearer <TOKEN>"  # Chunk 2.1: add auth
```

**Expected Response (200 OK):**
```json
[
    {
        "id": "uuid-1",
        "status": "PENDING",
        "priority": "MEDIUM",
        "reason_codes": ["validation_error"],
        "normalized_record": {
            "id": "uuid",
            "facility_name": null,
            "scope_1_emissions": 1000.00,
            "is_valid": false,
            "validation_errors": [
                {
                    "field": "facility_name",
                    "error": "Facility name is required"
                }
            ]
        },
        "created_at": "2023-11-15T10:00:00Z"
    },
    ...
]
```

---

### Test 4: Analyst Approves a ReviewTask

**Setup:**
From Test 1, get one PENDING ReviewTask.

**Steps:**

1. Get task ID:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.review.models import ReviewTask

task = ReviewTask.objects.filter(status='PENDING').first()
print(f"Task ID: {task.id}")  # Save this
```

2. Approve the task:
```bash
curl -X POST http://localhost:8000/api/review/<TASK_ID>/approve/ \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "APPROVED",
    "notes": "Data looks valid despite validation error (approved by analyst)"
  }'
```

**Expected Response (200 OK):**
```json
{
    "status": "approved",
    "approval_id": "uuid",
    "message": "Record approved and created EmissionsDataPoint"
}
```

3. Verify in DB:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.review.models import ReviewTask, ReviewApproval
from breathe.apps.emissions.models import EmissionsDataPoint

task = ReviewTask.objects.get(id='<TASK_ID>')
print(f"Task status: {task.status}")  # Should be APPROVED
print(f"Approved by: {task.approved_by.email}")
print(f"Approved at: {task.approved_at}")

# Check immutable approval record
approval = ReviewApproval.objects.get(review_task_id=task)
print(f"Approval record: {approval.id}")
print(f"Decision: {approval.decision}")
print(f"Analyst: {approval.analyst.email}")

# Check EmissionsDataPoint created
emissions = EmissionsDataPoint.objects.get(normalized_record_id=task.normalized_record_id)
print(f"EmissionsDataPoint created: {emissions.id}")

exit()
```

**Expected Output:**
```
Task status: APPROVED
Approved by: alice@company.com
Approved at: 2023-11-15T10:05:00Z
Approval record: <uuid>
Decision: APPROVED
Analyst: alice@company.com
EmissionsDataPoint created: <uuid>
```

---

### Test 5: Analyst Rejects a ReviewTask

**Setup:**
From Test 1, get another PENDING ReviewTask.

**Steps:**

1. Reject the task:
```bash
curl -X POST http://localhost:8000/api/review/<TASK_ID>/reject/ \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "REJECTED",
    "notes": "Scope1 value looks suspicious (1000 is too round, might be placeholder)"
  }'
```

**Expected Response (200 OK):**
```json
{
    "status": "rejected",
    "approval_id": "uuid",
    "message": "Record rejected. Please re-submit with corrected data."
}
```

2. Verify in DB:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.review.models import ReviewTask, ReviewApproval

task = ReviewTask.objects.get(id='<TASK_ID>')
print(f"Task status: {task.status}")  # Should be REJECTED
print(f"Rejection reason: {task.rejection_reason}")

approval = ReviewApproval.objects.get(review_task_id=task)
print(f"Decision: {approval.decision}")  # REJECTED

# No EmissionsDataPoint should be created
from breathe.apps.emissions.models import EmissionsDataPoint
emissions = EmissionsDataPoint.objects.filter(
    normalized_record_id=task.normalized_record_id
).exists()
print(f"EmissionsDataPoint exists: {emissions}")  # False

exit()
```

---

### Test 6: Override Previous Decision (Create New Approval)

**Setup:**
From Test 4, we approved a task. Now analyst realizes they made a mistake.

**Steps:**

1. Get the approved task:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.review.models import ReviewTask

# Find an APPROVED task
task = ReviewTask.objects.filter(status='APPROVED').first()
print(f"Task ID: {task.id}")
print(f"Previously approved by: {task.approved_by.email}")

exit()
```

2. Create new approval record to override:
```bash
curl -X POST http://localhost:8000/api/review/<TASK_ID>/override/ \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "REJECTED",
    "notes": "Found error on review: facility name has invalid characters"
  }'
```

3. Verify both approvals exist (immutable):
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.review.models import ReviewApproval

approvals = ReviewApproval.objects.filter(review_task_id='<TASK_ID>')
print(f"Total approvals: {approvals.count()}")  # 2

for approval in approvals.order_by('created_at'):
    print(f"Decision: {approval.decision}, Analyst: {approval.analyst}, Time: {approval.created_at}")

# Expected:
# Decision: APPROVED, Analyst: alice, Time: 2023-11-15T10:05:00Z
# Decision: REJECTED, Analyst: alice, Time: 2023-11-15T10:10:00Z

exit()
```

---

### Test 7: Batch Approval

**Setup:**
From Test 1, should have 2-3 remaining PENDING ReviewTasks (after approving/rejecting some).

**Steps:**

1. Get task IDs:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.review.models import ReviewTask

tasks = ReviewTask.objects.filter(status='PENDING')[:3]
task_ids = [str(t.id) for t in tasks]
print(f"Task IDs: {task_ids}")

exit()
```

2. Batch approve:
```bash
curl -X POST http://localhost:8000/api/review/batch_approve/ \
  -H "Content-Type: application/json" \
  -d '{
    "task_ids": ["uuid-1", "uuid-2", "uuid-3"],
    "decision": "APPROVED",
    "notes": "Batch reviewed and approved"
  }'
```

**Expected Response (200 OK):**
```json
{
    "status": "success",
    "approved_count": 3,
    "message": "Approved 3 records"
}
```

3. Verify:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.review.models import ReviewTask

pending = ReviewTask.objects.filter(status='PENDING').count()
approved = ReviewTask.objects.filter(status='APPROVED').count()
print(f"Pending: {pending}, Approved: {approved}")  # All moved to APPROVED

exit()
```

---

### Test 8: Analyst Metrics

**Setup:**
After running Tests 3-7, should have multiple approvals/rejections.

**Steps:**

```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.review.models import ReviewApproval
from django.contrib.auth.models import User
from django.db.models import Count, Q

analyst = User.objects.get(email='alice@company.com')

# Approval rate
all_decisions = ReviewApproval.objects.filter(analyst=analyst)
approved = all_decisions.filter(decision='APPROVED').count()
total = all_decisions.count()
approval_rate = (approved / total * 100) if total > 0 else 0

print(f"Alice's Approval Rate: {approval_rate:.1f}%")

# Review breakdown
breakdown = all_decisions.values('decision').annotate(count=Count('id'))
for item in breakdown:
    print(f"  {item['decision']}: {item['count']}")

# Audit trail sample
print(f"\nAudit trail (last 5 decisions):")
for approval in all_decisions.order_by('-created_at')[:5]:
    print(f"  {approval.created_at}: {approval.decision} - {approval.notes}")

exit()
```

**Expected Output:**
```
Alice's Approval Rate: 66.7%
  APPROVED: 2
  REJECTED: 1
  
Audit trail (last 5 decisions):
  2023-11-15T10:30:00Z: APPROVED - Batch reviewed and approved
  2023-11-15T10:25:00Z: APPROVED - Batch reviewed and approved
  2023-11-15T10:10:00Z: REJECTED - Found error on review: facility name has invalid characters
  ...
```

---

### Test 9: Data Audit Trail (Full Lineage)

**Setup:**
From previous tests, trace one record from CSV to EmissionsDataPoint.

**Steps:**

```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import RawIngestion, ParsedRecord, NormalizedRecord
from breathe.apps.review.models import ReviewTask, ReviewApproval
from breathe.apps.emissions.models import EmissionsDataPoint

# Start with an ingestion
ingestion = RawIngestion.objects.first()

# Follow one row through the pipeline
parsed_record = ParsedRecord.objects.filter(ingestion_id=ingestion).first()
print(f"1. ParsedRecord {parsed_record.id}: raw_values={parsed_record.raw_values}")

normalized_record = NormalizedRecord.objects.get(parsed_record_id=parsed_record)
print(f"2. NormalizedRecord {normalized_record.id}: "
      f"facility_name={normalized_record.facility_name}, "
      f"is_valid={normalized_record.is_valid}")

if normalized_record.is_valid:
    # Auto-approved
    emissions = EmissionsDataPoint.objects.get(
        parsed_record_id=parsed_record
    )
    print(f"3. EmissionsDataPoint {emissions.id}: "
          f"facility_name={emissions.facility_name}, "
          f"status=AUTO_APPROVED")
else:
    # Required review
    review_task = ReviewTask.objects.get(normalized_record_id=normalized_record)
    print(f"3. ReviewTask {review_task.id}: status={review_task.status}")
    
    # Check approval history
    approvals = ReviewApproval.objects.filter(review_task_id=review_task)
    for i, approval in enumerate(approvals.order_by('created_at'), 1):
        print(f"   Approval {i}: {approval.decision} by {approval.analyst} at {approval.created_at}")
    
    if review_task.status == 'APPROVED':
        emissions = EmissionsDataPoint.objects.get(
            normalized_record_id=normalized_record
        )
        print(f"4. EmissionsDataPoint {emissions.id}: "
              f"facility_name={emissions.facility_name}, "
              f"approved_by={review_task.approved_by}")

exit()
```

**Expected Output:**
```
1. ParsedRecord <uuid>: raw_values={'Plant_Name': 'Plant A', 'Scope1_mtCO2e': '1000'}
2. NormalizedRecord <uuid>: facility_name=Plant A, is_valid=True
3. EmissionsDataPoint <uuid>: facility_name=Plant A, status=AUTO_APPROVED

(or if invalid:)

1. ParsedRecord <uuid>: raw_values={'Plant_Name': '', 'Scope1_mtCO2e': '1000'}
2. NormalizedRecord <uuid>: facility_name=None, is_valid=False
3. ReviewTask <uuid>: status=APPROVED
   Approval 1: APPROVED by alice at 2023-11-15T10:05:00Z
4. EmissionsDataPoint <uuid>: facility_name=None, approved_by=alice
```

---

### Test 10: Django Admin View

**Setup:**
All previous tests completed.

**Steps:**

1. Go to http://localhost:8000/admin/
2. Click "Review Tasks"
3. See list of tasks with columns: facility_name, status, priority, analyst
4. Click on a task to see details
5. Verify approval history visible

**Expected UI:**
- List view shows: Task ID, Status, Priority, Analyst, Created Date
- Detail view shows: Full task details + approval history
- Can see raw_values, validation_errors, approval notes

---

## Summary

**Coverage:**
- ✅ Test 1: Auto-create ReviewTask for invalid records
- ✅ Test 2: Auto-approve valid records (no ReviewTask)
- ✅ Test 3: List pending ReviewTasks (dashboard)
- ✅ Test 4: Approve a task (create EmissionsDataPoint)
- ✅ Test 5: Reject a task (no EmissionsDataPoint)
- ✅ Test 6: Override decision (immutable approval log)
- ✅ Test 7: Batch approval (multiple tasks at once)
- ✅ Test 8: Analyst metrics (approval rate, breakdown)
- ✅ Test 9: Data lineage (CSV → Emissions)
- ✅ Test 10: Django admin verification

**All tests passing confirms:**
- ✅ ReviewTask created correctly for invalid/low-quality records
- ✅ Approval/rejection endpoints working
- ✅ EmissionsDataPoint created on approval
- ✅ Immutable approval audit log
- ✅ Override workflow (new approvals override old)
- ✅ Batch operations working
- ✅ Metrics calculated correctly
- ✅ Full data lineage preserved
- ✅ Admin interface functional
