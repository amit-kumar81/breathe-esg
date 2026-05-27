# Chunk 3.3: File Upload & Ingestion UI - Integration Guide

## Overview

Upload page handles CSV file selection and submission. Review page shows ingestion progress and triggers parse/normalize workflow.

---

## File Structure

```
frontend/src/
├── pages/
│   ├── UploadPage.jsx          # CSV file upload form
│   ├── IngestionReviewPage.jsx # Progress tracking + workflow
│   └── ...
├── hooks/
│   └── useIngestions.js        # useUploadCSV, useParse, useNormalize
└── App.jsx                     # Routes: /upload, /ingest/:id
```

---

## Usage Flow

### Step 1: User Visits Upload Page

```
http://localhost:3000/upload

See:
- "Upload Emissions Data" title
- CSV file input
- Data Source ID text field
- CSV format help text
- Upload button (disabled until form is valid)
```

### Step 2: Select File

```
Click file input
→ System file picker opens
→ User selects emissions.csv
→ Input shows: "📄 emissions.csv"
→ Success message: "✓ File selected"
```

### Step 3: Enter Data Source ID

```
Click "Data Source ID" field
Type: "acme-corp-2023"
→ Field validates (required)
→ Upload button enables
```

### Step 4: Submit

```
Click "Upload CSV"
→ Button shows "Uploading..."
→ File is sent: POST /api/ingest/upload/
→ Backend returns: {
  "id": "abc-123-def",
  "step": "UPLOADED",
  "data_source_id": "acme-corp-2023"
}
```

### Step 5: Success Screen

```
See:
- Green success box: "✓ Upload Successful"
- Ingestion ID: abc-123-def
- Two buttons:
  - "Review & Parse" (primary)
  - "Upload Another" (secondary)

Click "Review & Parse"
→ Navigate to /ingest/abc-123-def
```

### Step 6: Review Page Loads

```
http://localhost:3000/ingest/abc-123-def

See:
- Ingestion ID: abc-123-def
- Status: UPLOADED
- Progress bar: 33% (1 of 3 steps)
- "Parse CSV" button
- CSV format help text
```

### Step 7: Trigger Parse

```
Click "Parse CSV"
→ Button shows "Parsing..."
→ POST /api/ingest/{id}/parse/
→ Backend processes CSV, returns:
{
  "step": "PARSED",
  "steps_completed": 2,
  "completion_percentage": 66,
  "sample_parsed_records": [
    {
      "facility": "Plant A",
      "scope_1_emissions": "500.5",
      ...
    },
    ...
  ]
}
```

### Step 8: Review Parsed Data

```
After parsing completes:
- Status updates to: PARSED
- Progress bar: 66%
- Table shows sample parsed records (first 10)
- "Normalize & Validate" button appears
- Sample data shows:
  - Facility names
  - Raw emissions values
  - Year
  - Validation status
```

### Step 9: Trigger Normalize

```
Click "Normalize & Validate"
→ Button shows "Normalizing..."
→ POST /api/ingest/{id}/normalize/
→ Backend validates + calculates quality scores
→ Returns:
{
  "step": "NORMALIZED",
  "completion_percentage": 100,
  "sample_normalized_records": [
    {
      "facility_name": "Plant A",
      "scope_1_emissions": 500.5,
      "data_quality_score": 85,
      "is_valid": true
    },
    ...
  ],
  "summary": {
    "total_records": 100,
    "valid_records": 95,
    "warning_records": 3,
    "error_records": 2
  }
}
```

### Step 10: Review Normalized Data

```
After normalization completes:
- Status: NORMALIZED
- Progress bar: 100%
- Green success message: "Normalization complete..."
- Normalized records table shows:
  - Facility names
  - Emissions (normalized)
  - Quality score
  - Valid flag
- Summary box shows:
  - Total: 100
  - Valid: 95
  - Warnings: 3
  - Errors: 2
```

---

## Example 1: Successful Upload & Parse Flow

```javascript
// User uploads valid CSV
1. File: emissions.csv (3 rows, all valid)
2. Data Source ID: test-upload-2024
3. Click Upload
4. Success: ID = xyz-789

// Navigate to review page
5. Click "Review & Parse"
6. Page loads with UPLOADED status
7. Click "Parse CSV"
8. See 3 parsed records in table
9. Status updates to PARSED, 66% complete

// Normalize
10. Click "Normalize & Validate"
11. All 3 rows valid
12. Quality scores: 90, 88, 92
13. Summary: 3 total, 3 valid, 0 warnings, 0 errors
```

---

## Example 2: Upload with Errors

```javascript
// User uploads CSV with issues
1. File: emissions_bad.csv (5 rows, 2 have errors)
2. Data Source ID: bad-data-2024
3. Click Upload
4. Success: ID = err-456

// Parse
5. Navigate to review page
6. Click "Parse CSV"
7. All 5 rows parsed (backend tries to salvage)
8. Table shows parsed values (some empty fields)

// Normalize
9. Click "Normalize & Validate"
10. Quality scores calculated:
    - Row 1: 85 (valid)
    - Row 2: 60 (warnings: missing scope_2)
    - Row 3: 90 (valid)
    - Row 4: 30 (error: invalid year)
    - Row 5: 40 (error: all fields missing)
11. Summary: 5 total, 2 valid, 1 warning, 2 errors
12. Analyst sees which records need review (Phase 3.4)
```

---

## Example 3: Duplicate Upload (Idempotency)

```javascript
// User uploads same file twice
1. File: emissions.csv
2. Data Source ID: acme-final-2024
3. Click Upload
4. Success: ID = first-upload-id

// Later, user uploads same file again
5. File: emissions.csv (same content)
6. Data Source ID: acme-final-2024 (same)
7. Click Upload
8. Backend:
   - Calculates SHA256 hash
   - Finds existing RawIngestion with same hash
   - Returns same ID: first-upload-id
9. User redirected to existing review page
10. No duplicate ingestion created
```

---

## Example 4: Invalid File Type

```javascript
// User tries to upload Excel file
1. File: emissions.xlsx (wrong type)
2. Click file input
3. Select emissions.xlsx
4. JavaScript validation:
   - Check: file.name.endsWith('.csv')
   - Result: false
5. Alert: "Only .csv files are allowed"
6. File input cleared
7. User must select .csv file
```

---

## Code Examples

### Using useUploadCSV Hook

```javascript
const { mutate: upload, isPending, error, data } = useUploadCSV()

// On form submit
const handleSubmit = (e) => {
  e.preventDefault()
  upload({ file, dataSourceId }, {
    onSuccess: (ingestion) => {
      navigate(`/ingest/${ingestion.id}`)
    }
  })
}
```

### Using useParse Hook

```javascript
const { mutate: parse, isPending } = useParse(ingestionId)

const handleParse = () => {
  parse(null, {
    onSuccess: () => {
      // UI auto-updates because hook invalidates queries
    }
  })
}
```

### Conditional Rendering Based on Step

```javascript
const { data: ingestion } = useIngestionDetail(ingestionId)

const isParsed = ingestion?.step !== 'UPLOADED'
const isNormalized = ingestion?.step === 'NORMALIZED'

return (
  <>
    {!isParsed && <button onClick={parse}>Parse CSV</button>}
    {isParsed && !isNormalized && <button onClick={normalize}>Normalize</button>}
    {isNormalized && <p>✓ Complete</p>}
  </>
)
```

---

## Testing Checklist

```
Upload Page
- [ ] File input accepts .csv only
- [ ] .xlsx files rejected with alert
- [ ] Data Source ID is required
- [ ] Upload button disabled until valid
- [ ] Submit works with valid inputs
- [ ] Loading state shows "Uploading..."
- [ ] Success screen shows with ingestion ID
- [ ] "Review & Parse" button navigates to /ingest/:id
- [ ] "Upload Another" clears form

Review Page
- [ ] Loads with ingestion status
- [ ] Shows progress bar
- [ ] Shows UPLOADED status initially
- [ ] "Parse CSV" button works
- [ ] Sample records display after parse
- [ ] Status updates to PARSED
- [ ] Progress bar shows 66%
- [ ] "Normalize & Validate" button appears
- [ ] Normalize works
- [ ] Normalized records display
- [ ] Quality scores show
- [ ] Summary box shows totals
- [ ] Status shows NORMALIZED
- [ ] Progress bar shows 100%
```

---

## Common Patterns

### Show/Hide Buttons Based on State

```javascript
{ingestion.step === 'UPLOADED' && (
  <button onClick={parse}>Parse CSV</button>
)}
{ingestion.step === 'PARSED' && (
  <button onClick={normalize}>Normalize</button>
)}
{ingestion.step === 'NORMALIZED' && (
  <p>✓ Ready for review</p>
)}
```

### Display Sample Data in Table

```javascript
<table>
  <thead>
    <tr><th>Facility</th><th>Emissions</th></tr>
  </thead>
  <tbody>
    {ingestion.sample_parsed_records?.map((r, i) => (
      <tr key={i}>
        <td>{r.raw_values?.facility}</td>
        <td>{r.raw_values?.scope_1_emissions}</td>
      </tr>
    ))}
  </tbody>
</table>
```

### Progress Bar

```javascript
<div style={progressBarStyle}>
  <div style={{width: `${ingestion.completion_percentage}%`}}>
    Fill
  </div>
</div>
```

---

## Next Phase (3.4)

Analyst Review Dashboard will:
- List all normalized ingestions
- Show detailed error/warning messages
- Allow approve/reject for each record
- Create ReviewTasks for disputed records

IngestionReviewPage is readonly. Analysts interact in Phase 3.4.

---

This chunk completes the upload workflow UI. Users can upload CSVs, see progress, and prepare data for analyst review.

