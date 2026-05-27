# Chunk 2.2: Analyst Review Workflow API - Detailed Explanation

## Overview
Chunk 2.2 implements the **Analyst Review Workflow API** that sits between raw data ingestion and final emissions data publication. This chunk provides REST endpoints for analysts to review incoming emissions records, approve valid data, reject invalid submissions, and request clarification from data providers. The design emphasizes immutability, atomicity, and clear audit trails for compliance.

## Architecture Decision 1: Simple State Machine vs. Complex Escalation

### The Decision
We implement a **simple 4-state machine** (PENDING → APPROVED/REJECTED/PENDING_CHANGES) rather than a complex multi-level escalation (PENDING → ASSIGNED_TO_ANALYST → ASSIGNED_TO_MANAGER → ESCALATED_TO_QA → etc.).

### Why This Decision
**Simplicity and Maintenance Cost**: Each additional state adds paths, decision logic, and testing complexity. A team of 5-10 analysts reviewing 1000s of records per week doesn't need manager approval—that's governance overhead. If escalation is needed, it happens via ticket systems or meetings, not workflow state.

**Real-World Analyst Workflow**: Analysts follow a triage pattern:
1. See PENDING record → Is it valid? (check quality_score, validation_errors, data_quality_flags)
2. If YES → Approve immediately (move to APPROVED)
3. If NO but fixable → Request clarification (PENDING_CHANGES, data provider resubmits)
4. If NO and unfixable → Reject (REJECTED, log reason, analyst moves on)

**Speed**: A 3-state machine processes records faster than a 7-state machine with intermediate holds. Production systems prioritize throughput.

### Alternative Considered: Escalation Model
```
PENDING → ASSIGNED_TO_ANALYST → ASSIGNED_TO_MANAGER → ESCALATED_TO_LEGAL → REJECTED/APPROVED
```
**Why Rejected**: Adds 4+ intermediate states, requires assignment logic (which analyst?), requires manager oversight configuration, introduces queuing delays, requires role-based permissions. For MVP, this is premature complexity.

### How State Machine Looks
```
PENDING ──approve()──→ APPROVED (creates EmissionsDataPoint)
       ──reject()──→   REJECTED  (does NOT create EmissionsDataPoint)
       ──request_clarification()──→ PENDING_CHANGES (waits for resubmission)
```

---

## Architecture Decision 2: ReviewApproval Immutability

### The Decision
Once an analyst approves or rejects a record, that decision is immutable. You cannot undo or change an approval decision directly. Instead, you can create a new reviewal if needed (see "overturning a decision").

### Why This Decision
**Audit Trail Integrity**: If approvals could be edited, we can't trust the history. "Who approved this record?" becomes ambiguous if approvals can be modified. Immutability means the audit trail is a perfect record of what was decided when.

**Accountability**: An immutable record means the analyst who approved something is accountable for that decision. Editing it would blur responsibility.

**Data Integrity**: If we allowed "undo approval", we'd need to reverse the EmissionsDataPoint creation, which cascades to dependent calculations, reports, and exports. Immutability avoids this ripple effect.

**Regulatory Compliance**: ESG reporting is regulated. Immutable audit trails are a compliance requirement. Deletable or editable records would fail audit.

### Implementation
- `ReviewApproval` model has `created_at` but no `updated_at`
- `save()` method checks if `pk` exists; if yes, raises `IntegrityError`
- `delete()` always raises `IntegrityError`
- Only way to "overturn" a decision: create a new ReviewTask, analyst approves differently

### Alternative Considered: Editable Approval
```python
class ReviewApproval(models.Model):
    analyst = ForeignKey(User)
    decision = CharField(choices=['APPROVED', 'REJECTED', 'PENDING_CHANGES'])
    notes = TextField()
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)  # ← editable!
```
**Why Rejected**: Loses audit trail. If an analyst approves at 2pm and you change it to rejected at 4pm, what's the truth? The original approval, or the edit? Immutability removes this ambiguity.

---

## Architecture Decision 3: Status = PENDING_CHANGES, Not APPROVED_WITH_CHANGES

### The Decision
When an analyst requests clarification, the status becomes `PENDING_CHANGES`, not `APPROVED_WITH_CHANGES`. The semantics are: "Waiting for data provider to make changes, then resubmit."

### Why This Decision
**Clarity of Meaning**: 
- `APPROVED` = "This data is good, publish it"
- `REJECTED` = "This data is rejected, archive it"
- `PENDING_CHANGES` = "This data has issues, data provider needs to fix and resubmit"

If we used `APPROVED_WITH_CHANGES`, the meaning becomes muddy. Does approved mean "good to publish" or "good after changes"? Ambiguous status names lead to bugs.

**No EmissionsDataPoint Creation**: If status is PENDING_CHANGES, we do NOT create an EmissionsDataPoint yet. The record stays in the ingest pipeline awaiting resubmission. This ensures we don't accidentally publish incomplete data.

**Data Provider Workflow**: The data provider receives feedback: "Your submission has issues, please resubmit with fixes." They then upload a corrected file, which creates a new ReviewTask. The original ReviewTask stays in PENDING_CHANGES as history.

### Alternative Considered: Approved + Flag
```python
class ReviewTask(models.Model):
    status = CharField(choices=['APPROVED', 'REJECTED', 'PENDING'])
    is_approved_with_changes = BooleanField(default=False)
```
**Why Rejected**: Mixes two concerns. Is it approved? Is it approved-but-with-changes? When you query for approved records, do you include APPROVED_WITH_CHANGES? This creates ambiguity and bugs. Status should be single-valued and unambiguous.

---

## Architecture Decision 4: ReviewApproval as Separate Immutable Table

### The Decision
ReviewApproval is NOT a field on ReviewTask. It's a separate, immutable model that's created when an analyst makes a decision.

```python
class ReviewTask(models.Model):
    status = CharField(...)  # ← mutable, can change on clarification request
    # ...

class ReviewApproval(models.Model):
    review_task = ForeignKey(ReviewTask)
    analyst = ForeignKey(User)
    decision = CharField(choices=['APPROVED', 'REJECTED', 'FLAG_FOR_EXPERT'])
    # ← immutable, one per decision
```

### Why This Decision
**Separation of Concerns**: ReviewTask is "what's being reviewed" (mutable). ReviewApproval is "what decision was made" (immutable). Separating them prevents confusion.

**Decision History**: If approval is on ReviewTask, you can only see the latest decision. With a separate table, you see ALL decisions over time:
- Analyst A rejects (ReviewApproval #1)
- Data provider resubmits
- Analyst B approves (ReviewApproval #2)

This history is valuable for audits and understanding why something was finally approved.

**Immutability Isolation**: Keeping immutable data in its own table makes the design clearer. ReviewTask can be modified (status changes on clarification). ReviewApproval cannot (ever). This isn't a mixing of concerns.

### Alternative Considered: Single Table
```python
class ReviewTask(models.Model):
    status = CharField(...)
    analyst = ForeignKey(User)
    decision = CharField(...)
    approved_at = DateTimeField()
```
**Why Rejected**: Confuses mutable and immutable data. If status can change, how can analyst and decision remain unchanged? This leads to bugs where you forget to update analyst when status changes. Separate tables make the contract explicit.

---

## Architecture Decision 5: Atomic Transaction for Approval Action

### The Decision
The `approve()` endpoint wraps its entire operation in `transaction.atomic()`:
```python
with transaction.atomic():
    review_task.status = APPROVED
    review_task.save()
    ReviewApproval.objects.create(...)
    EmissionsDataPoint.objects.create(...)
    AuditLog.objects.create(...)
```

### Why This Decision
**All-or-Nothing**: If creating AuditLog fails, the EmissionsDataPoint is rolled back. You never end up with an approved ReviewTask but no EmissionsDataPoint. Consistency is guaranteed.

**Database Integrity**: If the server crashes mid-approval, the transaction is rolled back. You don't end up with partial approvals.

**Signal Safety**: Django signals fire during the transaction. If a signal fails, the transaction rolls back. This prevents data leaks where signals create partial state.

### Real Scenario Without Atomicity
1. Analyst approves record #1
2. ReviewTask.status = APPROVED ✓
3. ReviewApproval.objects.create() ✓
4. EmissionsDataPoint.objects.create() ← DATABASE FULL, error!
5. AuditLog.objects.create() ✓

**Result**: ReviewTask is approved, ReviewApproval exists, but NO EmissionsDataPoint. Data is inconsistent. Reports that count EmissionsDataPoints will be wrong.

**With Atomicity**: All 4 operations either all succeed or all rollback. No partial state.

### Alternative Considered: Manual Rollback
```python
try:
    review_task.status = APPROVED
    review_task.save()
    ReviewApproval.objects.create(...)
    EmissionsDataPoint.objects.create(...)
    AuditLog.objects.create(...)
except Exception as e:
    review_task.status = PENDING  # ← manual rollback
    review_task.save()
    raise
```
**Why Rejected**: Manual rollback is error-prone. You might forget to rollback all changes. Database transactions are built for this—use them.

---

## Architecture Decision 6: Flattened Serializer Output for Frontend

### The Decision
ReviewTaskListSerializer flattens emissions data so the frontend gets:
```json
{
  "id": "abc-123",
  "status": "PENDING",
  "priority": 1,
  "facility_name": "Plant A",
  "scope_1_emissions": 500.5,
  "scope_2_emissions": 200.0,
  "year": 2023,
  "error_count": 2,
  "flag_count": 1
}
```

NOT nested:
```json
{
  "id": "abc-123",
  "status": "PENDING",
  "normalized_record": {
    "normalized_values": {
      "facility_name": "Plant A",
      "scope_1_emissions": 500.5
    }
  }
}
```

### Why This Decision
**Frontend Simplicity**: React/Vue templates get `facility_name` directly, not `data.normalized_record.normalized_values.facility_name`. This simplifies templates and reduces nesting errors.

**Performance**: Flattening in the serializer (server-side) is faster than flattening in the browser (client-side JavaScript). Minimizes client-side code.

**Data Locality**: The fields most relevant to review (facility_name, scope_1_emissions, errors) are right there. Analysts don't drill into nested objects.

### Alternative Considered: Nested Serializer
```python
class ReviewTaskListSerializer(ModelSerializer):
    normalized_record = NormalizedRecordSerializer()
    # ← frontend drills into nested_record.normalized_values.facility_name
```
**Why Rejected**: Frontend becomes complicated. Templates have to dig into nested objects. More error-prone.

---

## Architecture Decision 7: BatchApproval with 1-100 Task Limit

### The Decision
The `batch_approve()` endpoint accepts a list of up to 100 task_ids and approves/rejects them all with the same decision.

```python
@action(detail=False, methods=['post'])
def batch_approve(self, request):
    serializer = BatchApprovalSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    task_ids = serializer.validated_data['task_ids']
    if len(task_ids) > 100:
        raise ValidationError("Max 100 tasks per batch")
    # Approve all atomically
```

### Why This Decision
**Analyst Efficiency**: An analyst reviewing 1000 similar records shouldn't need to click "approve" 1000 times. Batch operations let them group-approve records (e.g., all records from the same facility in 2023).

**Atomicity at Scale**: Batch operations are atomic. Either all 100 approve or none do. This prevents partial batches.

**Limit (100) Prevents Abuse**: Without a limit, an analyst could approve 10,000 records in one click, bypassing quality checks. A 100-task limit keeps batch operations reasonable while still improving efficiency.

**Rejection Tracking**: Each approved task creates a ReviewApproval and AuditLog entry. The batch operation is logged, not anonymized. We know exactly which analyst approved which records.

### Real Scenario
1. Data provider uploads 500 records for Plant A, 2023
2. System parses, normalizes, auto-approves 400 (is_valid=True, quality_score≥80)
3. 100 remain PENDING (is_valid=False or quality_score<80)
4. Analyst looks at a sample of 100, notices they all have the same issue: "Year is 2022, not 2023"
5. Analyst rejects all 100 in one batch_approve() call with decision=REJECTED and notes="Year mismatch"
6. Data provider sees the feedback, fixes the year, resubmits

Without batching: Analyst clicks "reject" 100 times manually. With batching: one API call.

### Alternative Considered: Unlimited Batch
```python
def batch_approve(self, request):
    task_ids = request.data['task_ids']  # ← no limit!
    # Approve all
```
**Why Rejected**: 
- An analyst could accidentally approve 50,000 records in one call
- The operation becomes too heavy (50k database writes in one transaction)
- If an error occurs midway, rolling back 50k writes is expensive
- A limit keeps operations manageable

---

## Architecture Decision 8: Decision History Queryable from ReviewTask Detail

### The Decision
The ReviewTaskDetailSerializer includes `decision_history` (all ReviewApproval entries for that ReviewTask):
```json
{
  "id": "task-1",
  "status": "APPROVED",
  "decision_history": [
    {
      "analyst_name": "alice",
      "decision": "REJECTED",
      "notes": "Year mismatch",
      "created_at": "2026-05-20T10:00:00Z"
    },
    {
      "analyst_name": "bob",
      "decision": "APPROVED",
      "notes": "Fixed, looks good",
      "created_at": "2026-05-21T14:00:00Z"
    }
  ]
}
```

### Why This Decision
**Transparency**: An analyst wanting to approve a record can see why it was rejected before. Maybe analyst A rejected it for a reason analyst B missed.

**Learning**: If alice rejected 10 times and then bob approved the next submission, bob learns what alice was looking for.

**Compliance**: Regulators ask "Why was this record approved?" The decision history answers that question.

**Dispute Resolution**: If there's disagreement about whether a record should have been approved, you can trace the approvals chronologically.

### Alternative Considered: Hide History
```python
class ReviewTaskDetailSerializer(ModelSerializer):
    # ← no decision_history field
```
**Why Rejected**: Analysts can't see why a record was previously rejected. They might make the same mistake again. History is context.

---

## Architecture Decision 9: No Direct Status Update on ReviewTask

### The Decision
You cannot PATCH `/api/review/{id}/` and set status directly. Status changes ONLY through custom actions (`approve()`, `reject()`, `request_clarification()`).

```python
class ReviewTaskViewSet(ModelViewSet):
    def perform_update(self, serializer):
        # ← this is called by PATCH, but status is read_only in serializer
        raise ValidationError("Use approve/reject/request_clarification instead")
```

### Why This Decision
**Intent Clarity**: The custom actions make intent explicit. `POST /api/review/1/approve/` is unambiguous. A PATCH with status=APPROVED might be a typo.

**Side Effects**: Approving a record should create ReviewApproval, EmissionsDataPoint, and AuditLog. If you let PATCH update status directly, analysts might forget to call the approval logic. Custom actions bundle everything.

**Permission Checks**: Custom actions can enforce rules:
```python
def approve(self, request, pk):
    if request.user.role != 'analyst':
        raise PermissionDenied()
    # ...
```
Direct PATCH updates are harder to guard.

### Alternative Considered: Allow PATCH Status Update
```python
# PATCH /api/review/1/
{
  "status": "APPROVED"
}
```
**Why Rejected**: Doesn't create ReviewApproval, EmissionsDataPoint, or AuditLog. The record is "approved" in status but not actually in the system. Leads to bugs.

---

## Architecture Decision 10: Analyst Name from User.username, Not Hardcoded

### The Decision
ReviewApprovalSerializer includes `analyst_name` which is derived from the analyst user's username:
```python
class ReviewApprovalSerializer(ModelSerializer):
    analyst_name = SerializerMethodField()
    
    def get_analyst_name(self, obj):
        return obj.analyst.username
```

### Why This Decision
**Decoupling**: ReviewApproval stores `analyst_id` (foreign key to User). When serializing, we fetch the username dynamically. If a user changes their username, the current ReviewApproval serialization reflects it.

**No Denormalization**: We don't store `analyst_name` as a CharField on ReviewApproval. That would require updating the field every time the user changes their name (messy).

**Flexibility**: Different clients can format the name differently. One client might want full_name, another wants username. A SerializerMethodField handles that.

### Alternative Considered: Store Name on Approval
```python
class ReviewApproval(models.Model):
    analyst = ForeignKey(User)
    analyst_name = CharField()  # ← denormalized copy
```
**Why Rejected**: If user changes username, analyst_name becomes stale. We'd need a signal to keep it updated. Extra complexity. SerializerMethodField is simpler.

---

## Architecture Decision 11: Auto-Approval for High-Quality Valid Records

### The Decision
Outside this chunk (in the ingest pipeline), records with `is_valid=True` and `quality_score≥80` are automatically marked as APPROVED without an analyst reviewing them.

```python
# In ingest pipeline
if normalized_record.is_valid and normalized_record.data_quality_score >= 80:
    review_task.status = 'AUTO_APPROVED'
    review_task.auto_approved = True  # ← flag for tracking
```

### Why This Decision
**Efficiency**: Not every record needs human review. If a record has no validation errors and high quality, approve it automatically. Analysts focus on exceptions (is_valid=False or quality_score<80).

**Throughput**: If 90% of records are auto-approved, analysts can review the remaining 10% in detail instead of manually approving 90%.

**Consistency**: Automated approval is consistent. The system applies the same rules to every record, no human bias.

**Audit Trail**: AUTO_APPROVED records still create AuditLog entries with action="SYSTEM_AUTO_APPROVED", so regulators can see they were auto-approved.

### Real Scenario
- Data provider uploads 1000 records
- System parses and validates: 900 are valid, 100 have errors
- Of 900 valid: 800 have quality_score≥80, 100 have quality_score<80
- Result: 800 auto-approved, 200 PENDING (requiring analyst review)
- Analyst reviews 200 records in 1 hour instead of 1000 records in 10 hours

### Alternative Considered: Everything Requires Review
```python
# All records stay PENDING until an analyst reviews
review_task.status = 'PENDING'
```
**Why Rejected**: Bottleneck. If you have 10,000 records per month and 2 analysts, it's impossible to keep up. Auto-approval for high-quality records is necessary.

---

## Architecture Decision 12: Request Clarification Doesn't Reject

### The Decision
When an analyst calls `request_clarification()`, the status becomes `PENDING_CHANGES` but the original ReviewApproval entries for rejection remain. It's not a rejection; it's a request for more information.

```python
@action(detail=True, methods=['post'])
def request_clarification(self, request, pk):
    review_task = self.get_object()
    review_task.status = 'PENDING_CHANGES'
    review_task.save()
    
    ReviewApproval.objects.create(
        review_task=review_task,
        analyst=request.user,
        decision='FLAG_FOR_EXPERT',  # ← not REJECTED
        notes=request.data['notes']
    )
    # Don't create AuditLog with action=REJECTED
    # Instead, action=FLAGGED_FOR_REVIEW
```

### Why This Decision
**Distinction from Rejection**: Rejection (REJECTED) means "This data is bad, don't use it." Flagging for clarification (PENDING_CHANGES) means "This data might be good, but I need more info." They're different outcomes.

**Data Provider Workflow**: 
- REJECTED → data provider archives it, finds new data source
- PENDING_CHANGES → data provider fixes issues, resubmits

**Metrics**: Reports can distinguish:
- "50% of submissions are rejected" (bad source quality)
- "20% of submissions need clarification" (moderate quality, fixable)

Conflating them hides whether your data sources are improving.

### Alternative Considered: Include Clarification in Rejection
```python
class ReviewApproval(models.Model):
    decision = CharField(choices=['APPROVED', 'REJECTED', 'REJECTED_WITH_FEEDBACK'])
```
**Why Rejected**: Muddies the meaning of rejection. If 20% of decisions are "rejected with feedback", is that a success or a failure? It's unclear.

---

## Key Principles Summary

1. **Immutability of Decisions**: Once an analyst approves/rejects, that decision is permanent. Accountability is clear.
2. **Atomic Transactions**: Approve/reject operations touch multiple tables. All succeed or all rollback.
3. **Simple State Machine**: 4 states (PENDING, APPROVED, REJECTED, PENDING_CHANGES). No complex escalations.
4. **Audit Trail First**: Every decision creates ReviewApproval and AuditLog. Regulators can see everything.
5. **Flattened Data**: Serializers flatten nested objects for frontend simplicity.
6. **Explicit Intents**: Custom actions (approve, reject, clarify) are explicit. Not ambiguous PATCH updates.
7. **Efficiency**: Batch operations and auto-approval for high-quality records save analyst time.
8. **Separation of Concerns**: ReviewTask (mutable) and ReviewApproval (immutable) are separate models.

---

## Testing Strategy

This chunk is validated through 10+ integration tests (see INTEGRATION_GUIDE):

1. **Pending List Endpoint**: GET `/api/review/pending/` returns PENDING tasks sorted by priority
2. **Approve Creates All Records**: POST approve() creates ReviewApproval, EmissionsDataPoint, AuditLog atomically
3. **Reject Doesn't Create EmissionsDataPoint**: POST reject() creates ReviewApproval and AuditLog but NOT EmissionsDataPoint
4. **Request Clarification Loops**: POST request_clarification() sets status to PENDING_CHANGES, data provider resubmits
5. **Decision History Queryable**: GET detail endpoint includes decision_history with all ReviewApprovals
6. **Batch Approve**: POST batch_approve() processes 1-100 tasks atomically with same decision
7. **Batch Reject**: Batch reject works for REJECTED decision
8. **Clarification Counts**: Metrics count PENDING_CHANGES as "needs provider action", not "rejected"
9. **Analyst Name from User**: ReviewApproval includes analyst_name derived from User.username
10. **Immutability Enforced**: Attempting to update ReviewApproval raises error

---

## Files in This Chunk

```
breathe/apps/review/
  ├── models.py (ReviewTask, ReviewApproval)
  ├── serializers.py (5 serializers as described)
  ├── views.py (ReviewTaskViewSet with 5 custom actions)
  ├── filters.py (ReviewTaskFilter with status, priority, facility_name)
  ├── urls.py (DefaultRouter registering viewset)
  ├── admin.py (Django admin for ReviewTask, ReviewApproval)
  ├── apps.py (AppConfig)
  └── __init__.py
```

---

## Next Steps

After Chunk 2.2 is complete and tested:

**Chunk 2.3: Multi-Tenancy Isolation**
- Implement JWT authentication (djangorestframework-simplejwt)
- Create UserProfile model (User ← → Tenant association)
- Update TenantAwareManager to filter QuerySets by request.user.tenant
- Add tenant filtering to all views (ReviewTaskViewSet, EmissionsDataPointViewSet, etc.)
- Implement permission checks: analyst can only review tasks in their tenant

**Chunk 2.4: Ingestion Workflow Endpoints**
- Orchestrate upload → parse → normalize → review pipeline
- Implement `/api/ingest/upload/` endpoint accepting CSV files
- Chain: UploadTask → CSVParser → Normalizer → ReviewTask creation
- Implement `/api/ingest/status/{upload_id}/` to track ingestion progress

**Chunk 2.5: Data Export & Reporting**
- Implement `/api/emissions/export/` with CSV/JSON export
- Support filtering by facility, year, status, quality score
- Generate summary reports (total emissions by scope, by year, by facility)

This chunk is production-ready, focusing on analyst workflow, immutable audit trails, and system resilience through transactions.
