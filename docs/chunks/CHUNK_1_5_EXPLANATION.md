# Chunk 1.5: Analyst Review & Approval Workflow — Complete Explanation

## Overview

**What This Chunk Does:**
- Creates ReviewTask records for normalized data requiring human approval
- Implements analyst review endpoints (`POST /api/ingest/{id}/approve/`, etc.)
- Converts approved NormalizedRecords into final EmissionsDataPoints
- Tracks approval decisions with full audit trail
- Implements rejection workflow (can re-submit for review)
- Calculates approval metrics (approval rate, avg review time)

**Why This Chunk Exists:**
Not all data is automatically valid. High-value emissions records, records with errors, or records below quality threshold require human analyst review. This chunk implements the **gate** between normalized data and final analytics-ready data.

**Key Principle:**
Every approval is audited. Analysts can see exactly which records they approved, when, and why. Rejections create feedback loop (resubmit to normalization).

---

## Architecture Decisions & Tradeoffs

### 1. Separate ReviewTask vs. Direct Approval on NormalizedRecord

**Decision:** Create separate ReviewTask model instead of adding approval fields directly to NormalizedRecord.

**Tradeoffs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Separate ReviewTask (chosen)** | Flexible: task can wait, be reassigned, tracked separately | Extra model, more joins |
| **Approval fields on NormalizedRecord** | Simpler: all data in one place | Tight coupling: record can't exist without approval state |

**Why Separate Model:**
- **Workflow flexibility**: Task can be reassigned to different analyst
- **Parallel work**: Multiple analysts working on different tasks simultaneously
- **Audit trail**: ReviewTask tracks decision, NormalizedRecord stays immutable
- **Status tracking**: Task progresses through states (PENDING → APPROVED/REJECTED)

---

### 2. Three-Tier Approval (Valid → ReviewTask → EmissionsDataPoint)

**Decision:** Create three distinct records: NormalizedRecord → ReviewTask → EmissionsDataPoint.

**Data Flow:**
```
NormalizedRecord (is_valid flag)
    ↓
    ├─ If is_valid=True + quality_score > 80
    │   → Auto-create EmissionsDataPoint (no ReviewTask needed)
    │
    └─ If is_valid=False OR quality_score < 80
        → Create ReviewTask (awaits analyst decision)
            ↓
        Analyst Reviews (sees validation_errors, raw_values)
            ↓
        ├─ If APPROVED → Create EmissionsDataPoint
        └─ If REJECTED → Analyst provides feedback, loops back
```

**Tradeoffs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Three-tier (chosen)** | Automatic approval for high-quality, analyst only for questionable | Complexity: multiple models |
| **All records need approval** | Consistent, auditable | Bottleneck: analysts must approve everything |
| **No review layer** | Fastest, fewest records | Risk: invalid data enters analytics |

**Why Three-Tier:**
- **Scalability**: Auto-approve valid records, analyst reviews only ~5-10% that need attention
- **Efficiency**: Analysts focus on high-value decisions
- **Quality**: Prevents bad data from entering analytics

---

### 3. Immutable ReviewApproval (Audit Log)

**Decision:** ReviewApproval records are immutable. Once created, never modified.

**Pattern:**
```python
# Don't do this (mutable):
review_task.approved_by = analyst
review_task.approved_at = now()
review_task.save()  # Overwrites history

# Do this (immutable):
ReviewApproval.objects.create(
    review_task_id=review_task,
    analyst=analyst,
    decision='APPROVED',
    notes='Data looks good',
    created_at=now()  # Immutable timestamp
)
# Can't modify, can only create new records
```

**Tradeoffs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Immutable ReviewApproval (chosen)** | Audit trail: can't lose history | Can't "undo" decision, must create new approval |
| **Mutable ReviewTask** | Can override decisions | Loss of audit trail if overwritten |

**Why Immutable:**
- **Compliance**: ESG data requires full audit trail
- **Accountability**: Can see every decision ever made
- **Debugging**: If error found later, can see full history

---

## Implementation Walkthrough

### File 1: `review/models.py`

**ReviewTask Model:**
```python
class ReviewTask(models.Model):
    status = CharField(choices=['PENDING', 'APPROVED', 'REJECTED', 'PENDING_CHANGES'])
    priority = CharField(choices=['LOW', 'MEDIUM', 'HIGH'])
    reason_codes = JSONField()  # ['validation_error', 'low_quality']
    analyst_notes = TextField()
    approved_by = ForeignKey(User)
    approved_at = DateTimeField()
    rejection_reason = TextField()
```

**ReviewApproval Model (Immutable):**
```python
class ReviewApproval(models.Model):
    review_task_id = ForeignKey(ReviewTask)
    analyst = ForeignKey(User)
    decision = CharField(choices=['APPROVED', 'REJECTED', 'FLAG_FOR_EXPERT'])
    notes = TextField()
    created_at = DateTimeField(auto_now_add=True)  # Immutable
```

**Why Two Models?**
- ReviewTask: mutable, tracks current state (is it approved? by whom?)
- ReviewApproval: immutable, audit log (what decisions were made?)

---

### File 2: `review/serializers.py`

**ReviewTaskListSerializer** (for analyst dashboard):
```python
class ReviewTaskListSerializer(ModelSerializer):
    normalized_record = NormalizedRecordDetailSerializer(read_only=True)
    
    class Meta:
        model = ReviewTask
        fields = [
            'id', 'status', 'priority', 'reason_codes',
            'normalized_record', 'created_at'
        ]
```

**ApprovalSerializer** (for approval request):
```python
class ApprovalSerializer(Serializer):
    decision = CharField(choices=['APPROVED', 'REJECTED', 'FLAG_FOR_EXPERT'])
    notes = CharField(required=False)
    
    def validate_decision(self, value):
        if value == 'REJECTED' and not self.initial_data.get('notes'):
            raise ValidationError("Rejection requires notes")
        return value
```

---

### File 3: `review/views.py`

**ReviewTaskViewSet:**
```python
class ReviewTaskViewSet(ViewSet):
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """List all pending review tasks for analyst"""
        tasks = ReviewTask.objects.filter(
            status='PENDING',
            tenant_id=request.user.tenant_id
        )
        serializer = ReviewTaskListSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a review task"""
        task = ReviewTask.objects.get(id=pk)
        serializer = ApprovalSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        # Create immutable approval record
        approval = ReviewApproval.objects.create(
            review_task_id=task,
            analyst=request.user,
            decision='APPROVED',
            notes=serializer.validated_data.get('notes', '')
        )
        
        # Update task status
        task.status = 'APPROVED'
        task.approved_by = request.user
        task.approved_at = now()
        task.save()
        
        # Create final EmissionsDataPoint
        create_emissions_data_point(task.normalized_record_id, approved_by=request.user)
        
        return Response({"status": "approved", "approval_id": approval.id})
```

---

## Definition of Done — Chunk 1.5

- [x] ReviewTask model (status, priority, analyst metadata)
- [x] ReviewApproval model (immutable audit log)
- [x] Auto-create ReviewTasks for invalid records
- [x] Analyst dashboard: list pending tasks with priority/reason
- [x] Approval endpoint: `POST /api/review/{task_id}/approve/`
- [x] Rejection endpoint with feedback loop
- [x] Create EmissionsDataPoint from approved records
- [x] Immutable audit trail of all decisions
- [x] Quality metrics (approval rate, avg review time)
- [x] Multi-tenancy support (analyst only sees own tenant)

---

## Interview Questions & Answers

### Q1: Why create ReviewTask if you could just approve NormalizedRecord directly?

**Answer:**
**Workflow flexibility.** ReviewTask is a task queue.

**Problems with direct approval on NormalizedRecord:**
```python
# Tight coupling
class NormalizedRecord:
    is_valid = Boolean
    approved = Boolean  # Can't change after approval
    approved_by = User
    approved_at = DateTime

# Problem: What if analyst needs to reassign review to someone else?
# Problem: What if analyst approves, but later needs to change decision?
# Problem: All history is lost (can't see what changed)
```

**With separate ReviewTask:**
```python
# Decoupled
task = ReviewTask.objects.get(id=123)
task.assigned_to = analyst_2  # Reassign to different analyst
task.save()

# Decision is immutable (ReviewApproval), task can be modified
approval = ReviewApproval.objects.get(task_id=123)
# approval.approved_at is IMMUTABLE (can't change it)
# but task.assigned_to can change

# Audit trail shows:
# - 2023-11-01: Task assigned to Alice
# - 2023-11-02: Task reassigned to Bob
# - 2023-11-03: Bob approves (ReviewApproval created)
```

**Analogy:** Like GitHub issues. Issue is mutable (reassign, add labels), but every action is logged immutably.

---

### Q2: What if analyst approves a record, then finds it has errors?

**Answer:**
**Create a new ReviewApproval record to reverse the decision.**

Can't modify the original approval (immutable audit log).

**Process:**
```python
# Original decision (immutable)
approval_1 = ReviewApproval.objects.get(...)
# Can't change: approval_1.decision = 'REJECTED'

# Create new decision (reversal)
approval_2 = ReviewApproval.objects.create(
    review_task_id=task,
    analyst=analyst,
    decision='REJECTED',  # Override previous decision
    notes='Found error: facility_name has special characters'
)

# Audit trail shows both decisions
ReviewApproval.objects.filter(review_task_id=task).order_by('created_at')
# [approval_1 (APPROVED), approval_2 (REJECTED)]
# Shows decision was overturned with full reasoning
```

**Immutability Benefit:**
- No loss of history
- Full trace of what changed and when
- Compliance: "Why did we approve this?" Answer: "See approval_1"

---

### Q3: How do you decide which records go to ReviewTask vs. auto-approve?

**Answer:**
**Four criteria for auto-approval:**

```python
def should_create_review_task(normalized_record):
    """
    Returns True if record needs analyst review, False if auto-approve.
    """
    
    # Criterion 1: Has validation errors
    if normalized_record.validation_errors:
        return True  # Create ReviewTask
    
    # Criterion 2: Low data quality score
    if normalized_record.data_quality_score < 80:
        return True  # Create ReviewTask
    
    # Criterion 3: Missing optional-but-important fields
    if not normalized_record.scope_2_emissions and not normalized_record.scope_3_emissions:
        # Only Scope 1 (incomplete picture)
        if normalized_record.data_quality_score < 90:
            return True  # Create ReviewTask
    
    # Criterion 4: Flagged by automated check
    if 'needs_expert_review' in normalized_record.data_quality_flags:
        return True  # Create ReviewTask
    
    # Otherwise: auto-approve
    return False
```

**Tradeoff:**
- ✅ Auto-approve valid, high-quality: analyst doesn't waste time on obvious ones
- ❌ Risk: Miss edge cases (should have reviewed but didn't)
- ✅ Mitigation: Can lower threshold (auto-approve only if quality_score > 95)

---

### Q4: What if analyst rejects a record? Does it go back to parsing?

**Answer:**
**No. Back to normalization (Chunk 1.4), not parsing.**

**Workflow:**
```
CSV File
  ↓ [Parse]
ParsedRecords
  ↓ [Normalize]
NormalizedRecords
  ↓ [Review]
  ├─ APPROVED → EmissionsDataPoint (final)
  └─ REJECTED → loops back to Normalize (re-normalization)

Example rejection:
Analyst says: "Scope 1 emissions can't be zero. Either data is wrong or we need a different calculation method."

Process:
1. Admin updates DataSource.field_mapping or validation rules
2. Call /normalize/ endpoint again with same ParsedRecords
3. New NormalizedRecord created with updated rules
4. If still invalid, stays in ReviewTask queue
5. Analyst reviews again
```

**Why back to normalize, not parse?**
- Parse layer is only for CSV structure (dialect detection, column parsing)
- Normalize layer is for business logic (validation rules, field mapping)
- Admin changes business logic → re-normalize
- Admin changes CSV structure → re-parse

---

### Q5: How do you prevent analysts from approving too quickly?

**Answer:**
**No technical enforcement, but design for transparency.**

**Approach:**
```python
# Track approval speed
time_in_review = task.approved_at - task.created_at
if time_in_review < timedelta(seconds=10):
    # Approved too quickly? Maybe didn't review carefully
    logger.warning(f"Task {task.id} approved in {time_in_review} (suspiciously fast)")
```

**Dashboard Metrics:**
- Average time per decision (by analyst, by priority)
- Approval rate (what % does analyst approve vs. reject?)
- Override rate (how often does a later analyst reverse a decision?)

**Incentive Structure:**
- Show analyst: "You approve 99% of records. Industry average is 85%"
- Not accusatory, just transparent
- Analyst can adjust thresholds for what triggers review

**Future (Chunk X):**
```python
# Require minimum review time for high-value records
if normalized_record.total_emissions > $1M_equivalent:
    min_review_time = timedelta(minutes=5)
    if time_in_review < min_review_time:
        return ValidationError("High-value records require minimum 5-minute review")
```

---

### Q6: What if two analysts approve the same record?

**Answer:**
**Last approval wins, audit trail shows both.**

**Scenario:**
```
Task created: 2023-11-01
Alice approves: 2023-11-02 10:00
Bob approves: 2023-11-02 10:05
```

**Question:** Who owns the decision?

**Answer:** Bob (last one), but both are visible in audit trail.

**Code:**
```python
@action(detail=True, methods=['post'])
def approve(self, request, pk=None):
    task = ReviewTask.objects.get(id=pk)
    
    # Check if already approved
    if task.status == 'APPROVED':
        logger.warning(f"Task {pk} already approved by {task.approved_by}")
        # Could return 409 Conflict, or allow override
    
    # Create new approval (immutable)
    approval = ReviewApproval.objects.create(...)
    
    # Update task (mutable)
    task.status = 'APPROVED'
    task.approved_by = request.user  # Overwrites
    task.save()
    
    # Audit trail:
    ReviewApproval.objects.filter(task_id=pk)
    # [Alice's approval, Bob's approval] both visible
```

**Tradeoff:**
- ✅ Immutable: both approvals logged
- ❌ Mutable: last one wins (who is responsible?)
- ✅ Solution: Require explicit "override" flag in request

---

### Q7: How do you calculate approval metrics?

**Answer:**
**Aggregate ReviewApproval records by analyst, date, decision.**

**Metrics Example:**
```python
from django.db.models import Count, Q

# Approval rate (what % does analyst approve?)
analyst = User.objects.get(email='alice@company.com')
approvals = ReviewApproval.objects.filter(analyst=analyst)
approved_count = approvals.filter(decision='APPROVED').count()
total_count = approvals.count()
approval_rate = approved_count / total_count * 100

print(f"Alice: {approval_rate}%")  # "Alice: 87%"

# Average review time
reviews = ReviewTask.objects.filter(analyst=analyst, approved_by=analyst)
avg_review_time = reviews.aggregate(
    avg_time=Avg(F('approved_at') - F('created_at'))
)['avg_time']

print(f"Average review time: {avg_review_time}")  # "Average: 3 minutes 45 seconds"

# Override rate (how often is Alice's decision overturned?)
alice_approvals = ReviewApproval.objects.filter(analyst=analyst, decision='APPROVED')
overturned = 0

for approval in alice_approvals:
    later_approvals = ReviewApproval.objects.filter(
        review_task_id=approval.review_task_id,
        created_at__gt=approval.created_at
    )
    if later_approvals.exists() and later_approvals.first().decision != 'APPROVED':
        overturned += 1

override_rate = overturned / alice_approvals.count() * 100
print(f"Override rate: {override_rate}%")  # "Override: 5%"
```

---

### Q8: Can an analyst see other analysts' approvals?

**Answer:**
**Yes, for transparency. But only their own tenant's data.**

```python
# Alice (at Tenant A) can see:
ReviewApproval.objects.filter(
    tenant_id=alice.tenant_id  # All approvals in Tenant A
)
# Shows: approvals by Alice, Bob, Carol (all from Tenant A)
# Does NOT show: approvals from other tenants

# Alice cannot see:
ReviewApproval.objects.filter(
    tenant_id!=alice.tenant_id  # Other tenants (403 Forbidden)
)
```

**Transparency Benefit:**
- Alice can learn from Bob's decisions
- Can spot inconsistent approval patterns
- Builds team knowledge of what "good data" looks like

---

### Q9: What if normalization creates a NormalizedRecord but the analyst changes their mind later?

**Answer:**
**Can't change NormalizedRecord (immutable), but can change approval decision.**

**Scenario:**
```
1. NormalizedRecord created: facility_name="Plant A"
2. ReviewTask created
3. Alice approves
4. EmissionsDataPoint created with facility_name="Plant A"
5. Later: Alice finds out name should be "Facility A" not "Plant A"
```

**Solution:**
```python
# Can't change NormalizedRecord
normalized_record.facility_name = "Facility A"
normalized_record.save()  # WRONG! Violates immutability principle

# Instead: create new approval record
new_approval = ReviewApproval.objects.create(
    review_task_id=task,
    analyst=alice,
    decision='REJECTED',  # Override previous approval
    notes='Found error: facility name should be "Facility A" not "Plant A"'
)

# Result: loops back to normalization
# User/admin can either:
# a) Fix source CSV (re-upload)
# b) Adjust validation rules (change field_mapping)
# c) Fix in downstream systems (if data already exported)
```

**Key Design:**
- NormalizedRecord is immutable (source of truth)
- ReviewApproval decisions can be overridden (create new record)
- Full audit trail of all decisions

---

### Q10: How do you handle batch approvals?

**Answer:**
**Endpoint that approves multiple tasks at once with single decision.**

```python
@action(detail=False, methods=['post'])
def approve_batch(self, request):
    """Approve multiple review tasks at once"""
    
    serializer = BatchApprovalSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    
    task_ids = serializer.validated_data['task_ids']
    decision = serializer.validated_data['decision']
    notes = serializer.validated_data.get('notes', '')
    
    # Validate all tasks exist and are pending
    tasks = ReviewTask.objects.filter(
        id__in=task_ids,
        status='PENDING'
    )
    
    if tasks.count() != len(task_ids):
        return Response(
            {"error": f"Some tasks not found or not pending"},
            status=400
        )
    
    # Approve each task
    approved_count = 0
    for task in tasks:
        ReviewApproval.objects.create(
            review_task_id=task,
            analyst=request.user,
            decision=decision,
            notes=f"{notes} (batch approval)"
        )
        
        task.status = 'APPROVED'
        task.approved_by = request.user
        task.approved_at = now()
        task.save()
        
        create_emissions_data_point(task.normalized_record_id)
        approved_count += 1
    
    return Response({
        "status": "success",
        "approved_count": approved_count,
        "message": f"Approved {approved_count} records"
    })
```

**Tradeoff:**
- ✅ Analyst can approve multiple at once (faster)
- ❌ Risk: Approve without reviewing each one
- ✅ Mitigation: Require minimum review per record (enforced in UI)

---

## Edge Cases & Gotchas

### 1. ReviewTask Created But NormalizedRecord Deleted
→ Database constraint prevents this (ForeignKey with CASCADE).

### 2. Analyst Closes Browser During Review
→ Task remains PENDING, can resume later. ReviewApproval only created on decision.

### 3. Same NormalizedRecord Approved Twice
→ EmissionsDataPoint created twice (duplicate). Fix: use `get_or_create()`.

### 4. Analyst Approves, Then Realizes They're Not Authorized
→ Too late: ReviewApproval is immutable. Create new REJECTED approval to override.

---

## Summary

**Chunk 1.5 implements:**
- ✅ ReviewTask model (workflow, priority, status)
- ✅ ReviewApproval model (immutable audit log)
- ✅ Auto-create tasks for invalid/low-quality records
- ✅ Analyst dashboard (pending tasks, reasons)
- ✅ Approval endpoints (approve, reject, flag for expert)
- ✅ EmissionsDataPoint creation on approval
- ✅ Immutable audit trail (full decision history)
- ✅ Multi-tenancy (analyst only sees own tenant)
- ✅ Batch approval workflow
- ✅ Metrics (approval rate, review time, override rate)

**Key Principles:**
1. **Immutable decisions**: ReviewApproval can't be changed, only new ones created
2. **Mutable workflow**: ReviewTask can be reassigned, status updated
3. **Automatic approval**: Valid, high-quality records bypass analyst queue
4. **Feedback loop**: Rejections loop back to normalization
5. **Full transparency**: Every decision logged with analyst, timestamp, reason

**Next Chunk:** 2.1 - Real Authentication & Multi-Tenancy (JWT, user isolation)
