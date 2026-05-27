# Chunk 3.4: Analyst Review Dashboard - Detailed Explanation

## Overview

Analyst dashboard showing pending review tasks in a table. Analysts click to view details and approve/reject records with optional notes. Uses modal for detail view.

---

## Architecture Decision 1: Table-Based Task List vs. Card View

### The Decision
Use **HTML table** for pending tasks, not card grid.

```javascript
// ✅ Table (3.4):
<table>
  <tr><th>Facility</th><th>Scope 1</th><th>Action</th></tr>
</table>

// ❌ NOT card grid:
// <div style={{display: 'grid'}}>
// More space, harder to scan many rows
```

### Why
**Scannable**: Analyst sees 20+ rows at once in columnar format. Cards waste space.

**Sortable**: Tables naturally support sorting (future: add to Phase 4).

**Dense**: More information per screen.

---

## Architecture Decision 2: Modal Detail View

### The Decision
Clicking "Review" opens modal dialog with full record details and action buttons.

```javascript
// ✅ Modal (3.4):
<button onClick={() => setSelectedTaskId(id)}>Review</button>
{selectedTask && <Modal>{details}</Modal>}

// ❌ NOT new page:
// <a href={`/review/${id}`}>Review</a>
// Page navigation slower for quick reviews
```

### Why
**Inline**: Analyst doesn't leave table, quickly reviews and returns.

**Fast**: Modal is in-place, no page load.

**Context**: Can see list while reviewing (future: side-by-side in 4+).

---

## Architecture Decision 3: Color-Coded Quality Badges

### The Decision
Quality score displayed as color badge: Red <70, Yellow 70-79, Green 80+.

```javascript
// ✅ Color badge (3.4):
<span style={{backgroundColor: score < 70 ? 'red' : 'green'}}>
  {score}
</span>

// ❌ NOT text only:
// "Quality Score: 85"
// Color gives instant visual cue
```

### Why
**Instant Recognition**: Analyst sees at-a-glance which records need attention.

**Matches Thresholds**: 80+ is auto-approved (backend), so red flags issues.

---

## Architecture Decision 4: Approve/Reject with Optional Notes

### The Decision
Analyst approves/rejects with optional notes. Notes are for audit trail and communication.

```javascript
// ✅ Optional notes (3.4):
POST /api/review/{id}/approve/
{"notes": "Missing scope_2, accepted estimate from previous year"}

// ❌ NOT required:
// {"notes": ""} → Error
// Forces analyst to write even if not needed
```

### Why
**Flexibility**: Some approvals are straightforward, some need notes.

**Audit Trail**: Notes explain why analyst approved questionable records.

**Communication**: Data provider can read notes and improve next submission.

---

## Architecture Decision 5: Pagination Over Infinite Scroll

### The Decision
Table shows page of 20 tasks, "Previous/Next" buttons.

```javascript
// ✅ Pagination (3.4):
Page 1: 20 tasks
Next → Page 2: 20 tasks

// ❌ NOT infinite scroll:
// Analyst scrolls, 20 more load, keeps scrolling
// Easy to lose place
```

### Why
**Control**: Analyst controls when to load next page.

**Predictable**: Each page has fixed count.

**Performance**: Don't load all 1000 pending tasks.

---

## Architecture Decision 6: One Modal at a Time

### The Decision
Only one review task modal open at a time. Closing modal returns to list.

```javascript
// ✅ Single modal (3.4):
Click Review → Modal opens
Close modal → Back to list
Click another → New modal

// ❌ NOT stacking modals:
// Click Review A → Modal A opens
// Click Review B → Modal B opens
// Two modals confusing
```

### Why
**Clarity**: One task at a time, analyst focuses.

**Simplicity**: No complex state managing multiple modals.

---

## Architecture Decision 7: Status Filter (Pending Only, Hide Approved)

### The Decision
Default: Show PENDING only. No toggle to show approved (Phase 4: add filter if needed).

```javascript
// ✅ Pending only (3.4):
useReviewTasks({ status: 'PENDING' })

// ❌ NOT all statuses:
// Show PENDING, APPROVED, REJECTED in same table
// Confuses analyst (approved records don't need action)
```

### Why
**Focused**: Analysts only see actionable records.

**Efficiency**: No scrolling past approved records.

**Simple**: MVP doesn't need filter complexity.

---

## Architecture Decision 8: Quality Score on Every Row

### The Decision
Quality score is visible in table, not just in modal.

```javascript
// ✅ Score in table (3.4):
Facility | Scope 1 | Score | Action
Plant A  | 500    | 85    | Review

// ❌ NOT hidden in modal:
// Analyst doesn't see score until clicks Review
```

### Why
**Context**: Analyst knows record quality before opening modal.

**Triage**: Can identify high-risk (low score) vs. low-risk (high score) records.

**Efficiency**: Can prioritize review order.

---

## Architecture Decision 9: No Bulk Approve

### The Decision
Approve/reject one record at a time. No "bulk approve 10 records" yet.

```javascript
// ✅ One-by-one (3.4):
Click record → Review → Approve → Next

// ❌ NOT bulk:
// Select 10 records → Bulk Approve
// More complex UI, risk of accidental approvals
```

### Why
**Safety**: Each record reviewed individually, less risky.

**Simplicity**: Simpler UI and backend logic.

**MVP**: Add bulk actions in Phase 4+ if needed (unlikely for compliance).

---

## Architecture Decision 10: Reject Reason (Not Optional)

### The Decision
Rejection requires a reason. Approval allows optional notes.

```javascript
// ✅ Reject needs reason (3.4):
if (action === 'reject' && !notes) return Error

// ✅ Approve optional:
if (action === 'approve') upload(notes || '')

// Why: Analyst must explain why rejected (compliance)
```

### Why
**Accountability**: Rejection without reason is unclear.

**Data Provider**: Needs to know what to fix.

**Compliance**: Audit trail shows why data was rejected.

---

## Summary of Decisions

| Decision | Why | Trade-Off |
|----------|-----|-----------|
| **Table** | Scannable, sortable | Less visual |
| **Modal** | Fast, in-place | Can't see list while reviewing |
| **Color badges** | Instant visual cue | Color blind users (add text) |
| **Optional notes** | Flexibility | Some records under-documented |
| **Pagination** | Control, performance | Click "Next" each time |
| **Single modal** | Clarity, simplicity | Can't compare two records |
| **Pending only** | Focused | Approved records hidden |
| **Score visible** | Context, triage | Table width larger |
| **No bulk approve** | Safety, simplicity | More clicks for 100+ records |
| **Reject requires reason** | Accountability | Approval less strict |

---

This chunk completes the analyst review workflow. Analysts can now systematically review, approve, or reject records, building the audit trail needed for compliance.

