# Chunk 3.3: File Upload & Ingestion UI - Detailed Explanation

## Overview

Chunk 3.3 implements the CSV upload form and ingestion review workflow. Users upload CSV files, see progress through parse/normalize steps, and review results before data is submitted for analyst approval.

---

## Architecture Decision 1: Simple File Input vs. Drag-and-Drop

### The Decision
Use **standard `<input type="file" accept=".csv" />** with styled label. No drag-and-drop for MVP.

```javascript
// ✅ Simple file input (3.3):
<input type="file" accept=".csv" onChange={handleFileChange} />
<label>Click to select CSV file</label>

// ❌ NOT drag-and-drop:
// <div onDrop={handleDrop}>Drag files here</div>
// Extra complexity for MVP
```

### Why This Decision

**Simplicity**: Standard input works in all browsers, no extra libraries.

**Accessibility**: Native input works with screen readers.

**MVP Speed**: Focus on core workflow, not UX polish.

### When to Add Drag-and-Drop
If user feedback requests: "Users want to drag files". Then add React Dropzone library.

---

## Architecture Decision 2: Client-Side File Validation

### The Decision
Validate file extension (`.csv` only) before submitting.

```javascript
// ✅ Client validation (3.3):
if (!file.name.endsWith('.csv')) {
  alert('Only .csv files are allowed')
  return
}

// ❌ NOT skip validation:
// User uploads .xlsx, backend rejects with error
```

### Why This Decision

**UX**: Instant feedback before wasting upload bandwidth.

**Bandwidth**: Don't upload non-CSV files.

**Server**: Backend still validates (belt-and-suspenders).

---

## Architecture Decision 3: Two-Step Form (Upload + Review)

### The Decision
Separate upload and review into two pages:
1. **UploadPage**: File selection, submit
2. **IngestionReviewPage**: Progress tracking, parse/normalize controls

```javascript
// ✅ Two pages (3.3):
// Page 1: UploadPage
// → Upload file
// → Redirect to /ingest/{id}

// Page 2: IngestionReviewPage
// → Show progress
// → Parse button
// → Normalize button

// ❌ NOT all-in-one page:
// Single page with all steps
// Messy UX
```

### Why This Decision

**Clarity**: Each page has one job.

**Progress**: After upload succeeds, show specific ingestion ID.

**Reusability**: Can link to IngestionReviewPage later (e.g., retry parsing).

---

## Architecture Decision 4: Data Source ID as Deduplication Key

### The Decision
Require `data_source_id` (e.g., "acme-corp-2023") to identify and deduplicate uploads.

```javascript
// ✅ Data source ID (3.3):
POST /api/ingest/upload/
{
  "file": <binary>,
  "data_source_id": "acme-corp-2023"
}

// Backend: If same data_source_id + same file_hash already exists
// → Return existing ingestion_id (idempotent)

// ❌ NOT random ID:
// Every upload creates new ingestion
// Duplicate uploads → duplicate records
```

### Why This Decision

**Idempotency**: Same upload twice returns same ID, doesn't duplicate.

**User Intent**: User can identify their upload by meaningful name.

**Deduplication**: Backend prevents double-processing same file.

---

## Architecture Decision 5: Progress Tracking with Status Field

### The Decision
Show workflow progress using `step` field: UPLOADED → PARSED → NORMALIZED.

```javascript
// ✅ Step-based progress (3.3):
{
  "step": "PARSED",
  "steps_completed": 2,
  "completion_percentage": 66
}

// UI shows:
// Progress bar: ████░░░ 66%
// Status: PARSED
// Next action: Normalize button

// ❌ NOT generic status:
// {"status": "processing"}
// Unclear what's done, what's next
```

### Why This Decision

**Clarity**: User knows exactly which step completed.

**Action**: UI shows what button to click next.

**Feedback**: Progress bar shows percentage.

---

## Architecture Decision 6: Separate Parse and Normalize Actions

### The Decision
Two separate buttons/actions: "Parse CSV" then "Normalize & Validate".

```javascript
// ✅ Separate steps (3.3):
// Step 1: Parse
POST /api/ingest/{id}/parse/

// Step 2: Normalize
POST /api/ingest/{id}/normalize/

// Each can fail independently

// ❌ NOT automatic:
// Upload automatically triggers parse
// Parse automatically triggers normalize
// If any fail, user doesn't know where it broke
```

### Why This Decision

**Control**: User can see results of each step.

**Debugging**: If parse fails, user doesn't try normalize.

**Feedback**: User sees sample rows after parse, validates before normalizing.

---

## Architecture Decision 7: Sample Records Display

### The Decision
Show first N parsed/normalized records in table. Not all records (could be 100k+).

```javascript
// ✅ Sample records (3.3):
GET /api/ingest/{id}/
→ {
  "sample_parsed_records": [...first 10...],
  "sample_normalized_records": [...first 10...]
}

// ❌ NOT all records:
// JSON response with 100k records
// Slow, memory-heavy
```

### Why This Decision

**Performance**: Response is fast and small.

**UX**: User sees representative sample, validates before proceeding.

**Scaling**: Works with files of any size.

---

## Architecture Decision 8: Summary Stats (Totals, Not Detailed Errors)

### The Decision
Show summary: "95 valid, 3 warnings, 2 errors". Not detailed error list on this page.

```javascript
// ✅ Summary (3.3):
{
  "summary": {
    "total_records": 100,
    "valid_records": 95,
    "warning_records": 3,
    "error_records": 2
  }
}

// ❌ NOT detailed errors:
// { "errors": [{"row": 5, "field": "scope_1", "issue": "..."}...] }
// Too much info on one page
```

### Why This Decision

**Overview**: User gets high-level picture before diving in.

**Redirect to Review**: Analysts see detailed error messages in review page (Phase 3.4).

**Simplicity**: One page doesn't try to be everything.

---

## Architecture Decision 9: Success Card After Upload

### The Decision
After successful upload, show success screen with ingestion ID and next actions.

```javascript
// ✅ Success card (3.3):
if (data && !isPending) {
  return (
    <div>
      ✓ Upload Successful
      Ingestion ID: abc123
      <button>Review & Parse</button>
      <button>Upload Another</button>
    </div>
  )
}

// ❌ NOT silent success:
// Just redirect to review page
// User doesn't see ID
```

### Why This Decision

**Confirmation**: User sees upload succeeded.

**ID Display**: Can copy ingestion ID if needed.

**Options**: Upload another or review this one.

---

## Architecture Decision 10: Ingestion Detail Page Shows Progress

### The Decision
IngestionReviewPage displays current step and progress, not just static data.

```javascript
// ✅ Dynamic progress (3.3):
<div>Status: {ingestion.step}</div>
<ProgressBar value={ingestion.completion_percentage} />
<button onClick={parse}>Parse CSV</button> {/* Only if not parsed */}
<button onClick={normalize}>Normalize</button> {/* Only if parsed */}

// ❌ NOT static display:
// Show parsed records even if not yet parsed
// Confusing
```

### Why This Decision

**Clarity**: User knows what step they're on.

**Guidance**: Shows which button is available now.

**Status**: Progress bar shows overall completion.

---

## Summary of Decisions

| Decision | Why | Trade-Off |
|----------|-----|-----------|
| **Simple file input** | Works everywhere, fast | No drag-and-drop (add later) |
| **Client file validation** | Instant feedback, save bandwidth | Server still validates |
| **Two-step UI** | Clear workflow, reusable | More navigation |
| **Data source ID** | Deduplication, user-meaningful ID | Extra field to fill |
| **Step-based progress** | Clear status, next action visible | More complex tracking |
| **Separate parse/normalize** | User control, clear feedback | More clicks (2 instead of 1) |
| **Sample records** | Fast, scalable | User sees subset not all data |
| **Summary stats** | High-level overview | Detailed errors elsewhere |
| **Success card** | Confirmation, ID visibility | Extra step before review |
| **Dynamic progress display** | Prevents confusion | More state management |

---

This chunk completes the upload workflow UI. Data flows from file → ingestion → parsing → normalization → ready for analyst review (Phase 3.4).

