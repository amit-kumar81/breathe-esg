# Chunk 3.4: Analyst Review Dashboard - Integration Guide

## Setup

Update `src/App.jsx`:

```javascript
import ReviewPage from './pages/ReviewPage'

// In routes:
<Route path="/review" element={<ReviewPage />} />
```

---

## Usage Flow

### 1. Analyst Opens Review Dashboard

```
http://localhost:3000/review

See:
- Table of PENDING tasks
- Columns: Facility, Scope 1, Year, Quality, Action
- Quality scores color-coded (green/yellow/red)
- "Review" button on each row
```

### 2. Analyst Clicks Review

```
Click "Review" on Plant A
→ Modal opens with:
  - Facility name
  - Scope 1, 2, 3 emissions
  - Year
  - Quality score
  - Status
  - Approve and Reject buttons
```

### 3. Analyst Approves

```
Click "Approve" button
→ Notes input appears (optional)
→ Type notes (or leave empty)
→ Click "Submit"
→ POST /api/review/{id}/approve/
→ Modal closes
→ Task removed from table (auto-refreshed)
```

### 4. Analyst Rejects

```
Click "Reject" button
→ Notes input appears (required)
→ Type rejection reason
→ Click "Submit"
→ POST /api/review/{id}/reject/
→ Modal closes
→ Task removed from table
```

### 5. Pagination

```
If >20 pending tasks:
- Click "Next" → Load next page
- Click "Previous" → Load previous page
- Page indicator shows current page
```

---

## Code Examples

### Approve with Optional Notes

```javascript
const { mutate: approve } = useApproveTask(taskId)

const handleApprove = () => {
  approve(actionNotes, {  // Can be empty string
    onSuccess: () => {
      setSelectedTaskId(null)
    }
  })
}
```

### Reject with Required Notes

```javascript
const { mutate: reject } = useRejectTask(taskId)

const handleReject = () => {
  reject(rejectionReason, {  // Required, validated
    onSuccess: () => {
      setSelectedTaskId(null)
    }
  })
}
```

### Quality Badge Color

```javascript
function getQualityBadgeStyle(score) {
  if (score < 70) return {color: 'red'}
  if (score < 80) return {color: 'orange'}
  return {color: 'green'}
}
```

---

## Examples

### Example 1: Straightforward Approval

```
1. Analyst sees Plant A, Quality: 90
2. Clicks Review
3. Modal shows all data valid, high quality
4. Clicks Approve (no notes needed)
5. Modal closes
6. Plant A removed from table (now APPROVED status)
```

### Example 2: Approval with Notes

```
1. Analyst sees Plant B, Quality: 75
2. Clicks Review
3. Modal shows: Scope 2 estimated (missing actual data)
4. Clicks Approve
5. Notes: "Scope 2 estimated from previous year, acceptable"
6. Clicks Submit
7. Backend logs notes in audit trail
```

### Example 3: Rejection

```
1. Analyst sees Plant C, Quality: 30
2. Clicks Review
3. Modal shows: Multiple fields missing, invalid year
4. Clicks Reject
5. Notes required: "Missing scope 1, invalid year 0000"
6. Clicks Submit
7. Plant C removed, sent back to data provider
8. Data provider sees rejection reason, fixes, re-uploads
```

---

## Testing

```
✓ Table loads with pending tasks
✓ Quality badges color correctly (red <70, yellow <80, green 80+)
✓ Click Review opens modal
✓ Modal shows full record details
✓ Approve button shows optional notes input
✓ Reject button shows required notes input
✓ Submit approve → Task removed from table
✓ Submit reject → Task removed from table
✓ Close modal → Back to table
✓ Pagination works (Next/Previous buttons)
✓ API calls include analyst ID (from auth context)
✓ Approved records appear in /api/emissions/export/
```

---

## Status After Actions

| Action | Record Status | Audit Log |
|--------|---------------|-----------|
| Approve | APPROVED | analyst_name, timestamp, notes |
| Reject | REJECTED | analyst_name, timestamp, reason |

---

This chunk completes the analyst review workflow. Data now flows: Upload → Parse → Normalize → Review → Approve → Export.

