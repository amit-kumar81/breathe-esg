# Chunk 3.4: Analyst Review Dashboard - Quick Reference

## Overview

Table of pending review tasks. Analysts click to open modal, review details, and approve/reject with optional notes.

---

## Key Files

- `src/pages/ReviewPage.jsx` - Task table + detail modal
- `src/hooks/useReviewTasks.js` - useReviewTasks, useApproveTask, useRejectTask (from 3.1)
- `src/App.jsx` - Route: /review

---

## Features

✅ **Task Table** - Pending records with columns: Facility, Scope 1, Year, Quality, Action
✅ **Quality Badges** - Color-coded: Red <70, Yellow <80, Green 80+
✅ **Modal Detail View** - Full record details + approve/reject
✅ **Optional Approval Notes** - Audit trail
✅ **Required Rejection Notes** - Explain why
✅ **Pagination** - Next/Previous for large result sets
✅ **One-Click Review** - No bulk operations (MVP)

---

## Workflow

```
1. Analyst visits /review
2. See table of PENDING tasks
3. Click Review on any task
4. Modal opens with:
   - Facility name, emissions, year
   - Quality score
   - Full details
   - Approve/Reject buttons
5. Click Approve or Reject
6. Add notes (optional for approve, required for reject)
7. Submit
8. Modal closes, table auto-refreshes
9. Record removed (status changed)
```

---

## Quality Score Colors

| Score | Color | Meaning |
|-------|-------|---------|
| 80-100 | Green | Excellent, approve quickly |
| 70-79 | Yellow | Good, may have minor issues |
| 0-69 | Red | Poor, review carefully |

---

## Hooks

```javascript
useReviewTasks({ page, status })
useApproveTask(taskId)
useRejectTask(taskId)
```

---

## Actions

| Action | Notes | Result |
|--------|-------|--------|
| Approve | Optional (audit context) | Record status = APPROVED |
| Reject | Required (explain why) | Record status = REJECTED |

---

## Modal States

```
Normal:
- Approve button
- Reject button

After Approve clicked:
- Notes textarea (optional)
- Submit button
- Cancel button

After Reject clicked:
- Notes textarea (required)
- Submit button
- Cancel button
```

---

## Endpoints Used

```
GET /api/review/?status=PENDING&page=N  → Task list
POST /api/review/{id}/approve/          → Approve
POST /api/review/{id}/reject/           → Reject
```

---

## Principles

✅ **One-by-one review** - No bulk operations (safety)
✅ **Clear quality indicator** - Color badges
✅ **Required rejection reason** - Compliance/audit trail
✅ **Optional approval notes** - Flexibility
✅ **Modal over navigation** - Speed

---

Phase 3.4 completes analyst workflow. Next: Dashboard + Export (3.5), then Deployment (Phase 4).

