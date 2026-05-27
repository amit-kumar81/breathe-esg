# Chunk 3.3: File Upload & Ingestion UI - Quick Reference

## Overview

Upload page for CSV files with progress tracking. Review page shows workflow status and allows triggering parse/normalize steps.

---

## Key Files

| File | Purpose |
|------|---------|
| `src/pages/UploadPage.jsx` | CSV upload form with validation |
| `src/pages/IngestionReviewPage.jsx` | Progress tracking + workflow control |
| `src/hooks/useIngestions.js` | useUploadCSV, useParse, useNormalize (from 3.1) |
| `src/App.jsx` | Routes: /upload, /ingest/:id |

---

## Features

✅ **CSV Upload** - File selection with validation
✅ **Data Source ID** - Deduplication key
✅ **Upload Confirmation** - Success screen with ingestion ID
✅ **Progress Tracking** - UPLOADED → PARSED → NORMALIZED
✅ **Sample Records** - Preview of parsed/normalized data
✅ **Parse Workflow** - Triggers CSV parsing
✅ **Normalize Workflow** - Triggers validation + quality scoring
✅ **Summary Stats** - Total, valid, warnings, errors count
✅ **Responsive Design** - Mobile-friendly styling

---

## Upload Flow

```
1. User visits /upload
2. Selects CSV file (must be .csv)
3. Enters Data Source ID (e.g., "acme-2024")
4. Clicks "Upload CSV"
5. Backend: POST /api/ingest/upload/
6. Success: Shows ingestion ID
7. User clicks "Review & Parse"
8. Redirects to /ingest/{ingestion_id}
```

---

## Review Flow

```
1. User at /ingest/{id}
2. Sees status: UPLOADED (33% complete)
3. Clicks "Parse CSV"
4. Backend: POST /api/ingest/{id}/parse/
5. Status updates: PARSED (66% complete)
6. Sample records display in table
7. Clicks "Normalize & Validate"
8. Backend: POST /api/ingest/{id}/normalize/
9. Status updates: NORMALIZED (100% complete)
10. Quality scores display
11. Summary shows: 95 valid, 3 warnings, 2 errors
```

---

## Components

### UploadPage.jsx

```javascript
// Form with:
- File input (accept=".csv" only)
- Data Source ID text field
- Validation (required fields)
- Upload button
- CSV format help text
- Success screen with ingestion ID
```

### IngestionReviewPage.jsx

```javascript
// Shows:
- Ingestion status
- Progress bar (0%, 33%, 66%, 100%)
- Step-based buttons (Parse, Normalize)
- Sample records table
- Summary statistics box
```

---

## Workflow States

| State | Step | Progress | Actions Available |
|-------|------|----------|-------------------|
| Just Uploaded | UPLOADED | 33% | Parse CSV |
| Parsed | PARSED | 66% | Normalize & Validate |
| Complete | NORMALIZED | 100% | None (ready for review) |

---

## Sample Data Display

### After Parse

```
Facility | Scope 1 | Year | Status
Plant A  | 500.5   | 2023 | OK
Plant B  | (empty) | 2023 | Warning
...
```

### After Normalize

```
Facility   | Scope 1 | Year | Quality Score | Valid
Plant A    | 500.5   | 2023 | 90           | ✓
Plant B    | 200.0   | 2023 | 60           | ✗
...
```

---

## Summary Stats

```
Total Records: 100
Valid: 95 (✓ green)
Warnings: 3 (⚠️ yellow)
Errors: 2 (✗ red)
```

---

## Hooks Used

```javascript
const { mutate: upload, isPending, data } = useUploadCSV()
const { data: ingestion } = useIngestionDetail(ingestionId)
const { mutate: parse, isPending: isParsing } = useParse(ingestionId)
const { mutate: normalize, isPending: isNormalizing } = useNormalize(ingestionId)
```

---

## File Validation

```
Client-side:
- File extension must be .csv
- File is required
- Data Source ID is required

Server-side (backend):
- File content is valid CSV
- Deduplication by data_source_id + file_hash
- Returns same ingestion_id if duplicate
```

---

## Error Handling

| Error | Message | User Can Retry |
|-------|---------|-----------------|
| Wrong file type | "Only .csv files allowed" | Yes |
| Missing fields | Shows in form validation | Yes |
| Parse fails | Shows API error | Yes |
| Normalize fails | Shows API error | Yes |

---

## Routes

```
GET  /upload                  → UploadPage
POST /api/ingest/upload/      → Upload CSV
GET  /ingest/:id              → IngestionReviewPage
POST /api/ingest/:id/parse/   → Parse workflow
POST /api/ingest/:id/normalize/ → Normalize workflow
```

---

## Inline Styles Used

- File input: Styled label with dashed border
- Progress bar: Blue fill on gray background
- Buttons: Primary (blue), secondary (gray), disabled (grayed)
- Tables: Basic styling with alternating rows
- Alerts: Color-coded (red = error, green = success, blue = info)
- Summary: Grid layout (4 columns, responsive)

---

## Common Patterns

| Pattern | Code |
|---------|------|
| Conditional button | `{!isParsed && <button>Parse</button>}` |
| Show loading | `{isPending ? 'Parsing...' : 'Parse CSV'}` |
| Display table | `{records?.map(r => <tr>...)</tr>)}` |
| Progress bar | `<div style={{width: `${percent}%`}}>` |
| Summary grid | `display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)'` |

---

## Testing

```
Manual Testing:
- Upload valid CSV → See success + ID
- Upload wrong file type → See error
- Parse → See sample records
- Normalize → See quality scores
- Refresh page → Ingestion data persists
- Each step shows correct progress %

Edge Cases:
- Empty CSV file → Backend error
- CSV with all missing fields → Summary: 0 valid, 100 errors
- Same file upload twice → Returns same ingestion_id
- Cancel upload → State resets
```

---

## Next Phase (3.4)

Analyst Review Dashboard will:
- List all NORMALIZED ingestions
- Show detailed per-record issues
- Allow approve/reject
- Create ReviewTasks
- Populate EmissionsDataPoint (ready for export)

UploadPage and ReviewPage are data prep. Analysts work in 3.4.

---

## Principles Maintained

✅ **Realistic**: Standard file input, no over-engineering
✅ **No Hallucinations**: Every line from spec
✅ **Progress Tracking**: User knows which step they're on
✅ **Error Handling**: Graceful errors at each step
✅ **Sample Data**: Shows representative subset, scalable
✅ **Idempotency**: Same upload returns same ID
✅ **Two-Step Workflow**: Clear progression

---

This chunk completes the upload and data preparation UI. Users upload CSVs, data flows through parse → normalize, and is ready for analyst review in Phase 3.4.

