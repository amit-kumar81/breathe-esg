# Chunk 1.3: CSV Parser & ParsedRecord Generation — Complete Explanation

## Overview

**What This Chunk Does:**
- Takes a RawIngestion (original CSV text stored as raw_csv_content)
- Detects CSV dialect (delimiter: comma, semicolon, tab, pipe) using csv.Sniffer
- Parses CSV text into rows (list of dicts)
- For each row, creates a ParsedRecord (structured, unvalidated)
- Handles empty rows gracefully (logs error, skips row)
- Returns summary of parsing operation
- Enables idempotent re-parsing (same result every time)

**Why This Chunk Exists:**
RawIngestion stores raw data as original CSV text (single source of truth). We need to convert those rows into database records so we can:
- Link each row to its source with proper dialect detection
- Track errors per-row (not per-file)
- Prepare for normalization (Chunk 1.4)
- Enable row-level versioning and audit
- Re-parse safely if parsing logic changes (deterministic from immutable source)

**Key Principle:**
Do NOT validate or normalize yet. ParsedRecord stores raw_values exactly as received from CSV. Validation happens in Chunk 1.5.

---

## Architecture Decisions & Tradeoffs

### 1. CSV Dialect Detection (Handling Different Delimiters)

**Decision:** Auto-detect CSV dialect using Python's `csv.Sniffer`.

**Why This Matters:**
Different regions use different delimiters:
```
US/UK:     Plant,Scope1,Year      (comma)
Europe:    Plant;Scope1;Year      (semicolon, because comma is decimal separator)
Tab-sep:   Plant[TAB]Scope1[TAB]Year
```

**The Problem Without Detection:**
If we hardcode comma delimiter:
```csv
Plant;Scope1;Year
Plant A;1234,56;2023
Plant B;5678,90;2023
```

Parsing with hardcoded comma:
```python
# csv.DictReader with delimiter=','
[
    {"Plant;Scope1;Year": "Plant A;1234,56;2023"},  # WRONG! Didn't split on semicolon!
    {"Plant;Scope1;Year": "Plant B;5678,90;2023"}
]
```

**How Detection Works:**
```python
from csv import Sniffer
sample = csv_text[:8192]  # First 8KB
sniffer = Sniffer()
dialect = sniffer.sniff(sample)
delimiter = dialect.delimiter  # Detects ';' automatically
```

Result: Correct parsing regardless of delimiter!

**Tradeoffs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Auto-detect (chosen)** | Handles regional differences, user doesn't have to specify | Slight overhead (sample parsing), detection can fail |
| **User specifies delimiter** | No overhead, explicit | Bad UX (user must know their file), easy to pick wrong one |
| **Hardcode comma** | Simple, fast | Breaks for semicolon/tab delimited files (data loss!) |

**What Happens If Detection Fails?**
```python
try:
    dialect = sniffer.sniff(sample)
except csv.Error:
    # Fall back to comma
    dialect = csv.excel
    logger.warning("Could not detect dialect, defaulting to comma")
```

Safe fallback: comma is most common. User sees warning in logs if it was wrong.

---

### 2. Endpoint vs. Management Command vs. Signal

**Decision:** Implement as REST endpoint (`POST /api/ingest/{id}/parse/`)

**Alternatives Considered:**

| Approach | Pros | Cons |
|----------|------|------|
| **REST endpoint (chosen)** | User-driven, step-by-step flow, gives feedback | Requires HTTP requests, not automatic |
| **Django management command** | Batch processing, no HTTP overhead | Hard to integrate with UI, requires CLI |
| **Celery signal (async)** | Scalable, handles large files | Overkill for MVP, adds complexity |
| **Auto-trigger on upload** | Seamless, no extra step | Less control, hard to debug |

**Why REST Endpoint:**
- **Matches the roadmap**: upload → parse → normalize → review (each step deliberate)
- **User visibility**: Analyst can see parsing progress, errors, summary
- **Debuggable**: Can retry, inspect intermediate state
- **Future-proof**: Easy to add async later (change endpoint to return 202 + task_id)

---

### 2. Idempotency: Delete Old Records or Skip?

**Decision:** Delete existing ParsedRecords and recreate them (idempotent re-parsing).

**Scenario:**
```
User uploads data.csv → calls /parse → creates 100 ParsedRecords
User calls /parse again on same ingestion → delete 100, create 100 new ones
Result: Same 100 ParsedRecords, deterministic
```

**Why NOT skip (option B)?**

| Option | Behavior | Problem |
|--------|----------|---------|
| **Delete & recreate (chosen)** | Re-parsing regenerates records | If source data changes, new records overwrite old—need audit trail |
| **Skip if already parsed** | Don't re-parse if records exist | If parsing logic changes, can't update existing records |

**Solution for audit trail (Chunk 1.6):**
When ParsedRecords are created, an AuditLog entry is created (via Django signals). So:
- First parse: 100 ParsedRecords created → AuditLog: "ParsedRecord created"
- Re-parse: Old records deleted, new ones created → AuditLog: "ParsedRecord deleted", "ParsedRecord created"
- Analyst can see full history in audit log

**Tradeoff:**
- ✅ Allows logic updates: if parsing code changes, can re-parse
- ❌ Loses deleted records (mitigated by audit log)
- ✅ Deterministic: same input = same output
- ❌ Not immutable (mutable during parsing)

---

### 3. Where to Handle Empty Rows?

**Decision:** Reject empty rows (skip, log error, continue).

**Example:**
```csv
Plant_Name,Scope1_mtCO2e,Year
Plant A,1234.56,2023
,,                       <- Empty row
Plant B,2000.00,2023
```

Result: 2 ParsedRecords created, 1 error logged.

**Why Skip Empty Rows?**
- **No data**: All fields null = no useful information
- **Common in real CSVs**: Users add blank rows by mistake
- **Fail-safe**: Don't create empty records that break downstream logic
- **Visible error**: Logged and returned in summary

**Where to Define "Empty"?**
```python
def is_row_empty(row_dict):
    """Row is empty if all values are None, "", or whitespace"""
    for value in row_dict.values():
        if value and str(value).strip():
            return False  # Found non-empty value
    return True  # All empty
```

---

### 4. Raw Values: Store Exactly or Clean?

**Decision:** Store raw_values exactly as CSV provided (no cleaning).

**Example:**
```csv
Plant_Name,Scope1,Year
  Plant A  ,  1234.56  , 2023   <- Extra spaces
Plant B,1234.56,2023
```

**ParsedRecord created:**
```python
parsed_record.raw_values = {
    "Plant_Name": "  Plant A  ",   # Spaces preserved!
    "Scope1": "  1234.56  ",
    "Year": " 2023   "
}
```

**Why NOT clean?**
- **Auditable**: Can see exactly what came from CSV
- **Reversible**: If we trim and lose data, can't recover
- **Deferred**: Trimming is a normalization decision (Chunk 1.5)
- **Future-proof**: Different sources might want different trimming

**Cleaning Happens in Chunk 1.5:**
```python
# In normalization (Chunk 1.5)
normalized_value = raw_value.strip()  # Now trim it
```

---

### 5. Synchronous vs. Async Processing

**Decision:** Synchronous for MVP (no Celery yet).

**Processing Time:**
- 100 rows: ~100ms
- 10,000 rows: ~10 seconds
- 1,000,000 rows: ~15 minutes (problematic)

**Current Behavior:**
```
POST /api/ingest/{id}/parse/
  [Wait ~10 seconds for 10k rows]
  → 200 OK with summary
```

**When to Add Async (Chunk X):**
```python
# Future: if row_count > 50000:
from celery import shared_task

@shared_task
def parse_large_ingestion(ingestion_id):
    """Async: parse in background"""
    raw_ingestion = RawIngestion.objects.get(id=ingestion_id)
    parse_raw_ingestion(raw_ingestion)

# In view:
if raw_ingestion.line_count > 50000:
    task_id = parse_large_ingestion.delay(ingestion_id)
    return Response({
        "ingestion_id": ingestion_id,
        "status": "parsing_in_progress",
        "task_id": task_id,
        "message": "Large file queued. Check back later."
    }, status=202)  # Accepted, not yet processed
```

---

## Implementation Walkthrough

### File 1: Updated `serializers.py`

**New Serializers Added:**

#### `ParseRequestSerializer`
```python
class ParseRequestSerializer(serializers.Serializer):
    class Meta:
        fields = []  # No input needed (ingestion_id is in URL)
```

Purpose: Placeholder for consistency. API contracts should be explicit even if empty.

#### `ParseResponseSerializer`
```python
class ParseResponseSerializer(serializers.Serializer):
    ingestion_id = serializers.UUIDField()
    status = serializers.CharField()  # 'parsed' or 'already_parsed'
    total_rows = serializers.IntegerField()
    parsed_records_created = serializers.IntegerField()
    parsing_errors = serializers.ListField(child=serializers.CharField())
    message = serializers.CharField()
```

Purpose: Documents the response format for API documentation and type safety.

#### `ParsedRecordListSerializer` & `ParsedRecordDetailSerializer`
For viewing parsed records (Chunk 2.1 will use these in list/detail endpoints).

---

### File 2: Updated `utils.py`

**New Functions:**

#### `parse_raw_ingestion(raw_ingestion)`

**Signature:**
```python
def parse_raw_ingestion(raw_ingestion):
    """
    Convert RawIngestion.raw_content (list of dicts) into ParsedRecords.

    Returns:
        dict: {
            "parsed_count": int,
            "parsing_errors": list,
            "empty_rows": list
        }
    """
```

**Algorithm:**
```
1. Delete existing ParsedRecords (idempotent)
2. For each row_num, row_data in raw_content:
   a. Check if row is empty → log error, skip
   b. Create ParsedRecord:
      - source_row_number = row_num
      - raw_values = row_data
      - parsing_errors = []
   c. Increment parsed_count
3. Return summary
```

**Key Points:**
- Uses `enumerate(..., start=1)` so row numbers are 1-indexed (user-friendly)
- Empty row check: all fields are None or empty string
- Logs each step (debug for success, warning for errors)
- Continues on error (doesn't fail the entire operation)

#### `is_row_empty(row_dict)`

**Logic:**
```python
def is_row_empty(row_dict):
    for value in row_dict.values():
        if value is None or value == "":
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return False  # Found non-empty value
    return True  # All empty
```

**Why this definition?**
- Handles None (missing CSV field)
- Handles empty string (CSV field with "")
- Handles whitespace-only ("   ")
- Real data even if just whitespace is preserved in raw_values, but row is marked as empty

---

### File 3: Updated `views.py`

**New Action: `parse()`**

**Endpoint:** `POST /api/ingest/{ingestion_id}/parse/`

**Flow:**
```
1. Get RawIngestion by pk (ingestion_id from URL)
   → 404 if not found

2. Tenant isolation placeholder
   → In Chunk 2.3: verify request.user.tenant_id == raw_ingestion.tenant_id

3. Call parse_raw_ingestion(raw_ingestion)
   → Creates ParsedRecords
   → Returns result dict with parsed_count, errors, etc.

4. Format response
   → 200 OK with summary

5. Error handling
   → 500 if unexpected error during parsing
```

**Response Format:**
```json
{
    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "parsed",
    "total_rows": 100,
    "parsed_records_created": 100,
    "empty_rows": 0,
    "parsing_errors": [],
    "message": "Successfully parsed 100 of 100 rows"
}
```

**With Errors:**
```json
{
    "ingestion_id": "...",
    "status": "parsed",
    "total_rows": 102,
    "parsed_records_created": 100,
    "empty_rows": 2,
    "parsing_errors": [
        "Row 5: Empty row (all fields are null or empty)",
        "Row 87: Empty row (all fields are null or empty)"
    ],
    "message": "Successfully parsed 100 of 102 rows"
}
```

---

## Definition of Done — Chunk 1.3

- [x] REST endpoint: `POST /api/ingest/{ingestion_id}/parse/`
- [x] Converts RawIngestion rows → ParsedRecords
- [x] Stores source_row_number for traceability
- [x] Handles empty rows gracefully (logs error, skips)
- [x] Idempotent: re-parsing is safe (deletes old, creates new)
- [x] Returns summary with parsed count and error list
- [x] Proper error responses (404 if ingestion not found)
- [x] Logging at each step
- [x] Tenant isolation placeholder (ready for Chunk 2.3)
- [x] No validation yet (that's Chunk 1.5)

---

## Testing the Endpoint (Manual)

### Prerequisites

From Chunk 1.2, you should have:
- 1 Tenant
- 1 DataSource
- 1 RawIngestion with raw_content (list of dicts)

If not, follow CHUNK_1_2_INTEGRATION_GUIDE.md to create them.

### Test 1: Successful Parsing

```bash
# Get the ingestion_id from Chunk 1.2
# Let's say it's: 550e8400-e29b-41d4-a716-446655440000

curl -X POST http://localhost:8000/api/ingest/550e8400-e29b-41d4-a716-446655440000/parse/
```

**Expected Response (200 OK):**
```json
{
    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "parsed",
    "total_rows": 2,
    "parsed_records_created": 2,
    "empty_rows": 0,
    "parsing_errors": [],
    "message": "Successfully parsed 2 of 2 rows"
}
```

**Verify in DB:**
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import ParsedRecord

records = ParsedRecord.objects.all()
print(f"Total ParsedRecords: {records.count()}")  # Should be 2

for pr in records:
    print(f"Row {pr.source_row_number}: {pr.raw_values}")
```

### Test 2: Idempotent Re-Parsing

Call the same endpoint again:

```bash
curl -X POST http://localhost:8000/api/ingest/550e8400-e29b-41d4-a716-446655440000/parse/
```

**Expected Response (200 OK):**
Same as before (same parsed count, same records).

**Verify in DB:**
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import ParsedRecord

# Should still be 2 (not 4)
print(f"Total ParsedRecords: {ParsedRecord.objects.count()}")
```

### Test 3: Ingestion with Empty Rows

Create a CSV with empty rows:

```csv
Plant_Name,Scope1_mtCO2e,Year
Plant A,1234.56,2023
,,,
Plant B,2000.00,2023
,,
```

Upload this file (Chunk 1.2):
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@with_empty_rows.csv" \
  -F "data_source_id=<DS_ID>"
```

Get the new ingestion_id. Then parse it:

```bash
curl -X POST http://localhost:8000/api/ingest/<NEW_ID>/parse/
```

**Expected Response (200 OK):**
```json
{
    "ingestion_id": "...",
    "status": "parsed",
    "total_rows": 5,
    "parsed_records_created": 2,
    "empty_rows": 3,
    "parsing_errors": [
        "Row 2: Empty row (all fields are null or empty)",
        "Row 4: Empty row (all fields are null or empty)",
        "Row 5: Empty row (all fields are null or empty)"
    ],
    "message": "Successfully parsed 2 of 5 rows"
}
```

### Test 4: Non-existent Ingestion

```bash
curl -X POST http://localhost:8000/api/ingest/99999999-9999-9999-9999-999999999999/parse/
```

**Expected Response (404 Not Found):**
```json
{
    "error": "RawIngestion not found"
}
```

### Test 5: Verify in Django Admin

1. Go to http://localhost:8000/admin/
2. Click "Parsed Records"
3. Should see records from Test 1 (and Test 3 if you ran it)
4. Click into one:
   - source_row_number: 1 or 2
   - raw_values: {"Plant_Name": "Plant A", ...}
   - parsing_errors: [] (empty for valid rows)

---

## Interview Questions & Answers

### Q1: Why create ParsedRecords at all? Why not jump straight to normalization?

**Answer:**
ParsedRecord is a **layer of indirection** with three benefits:

**Benefit 1: Error Isolation**
```
If we go directly to normalization:
  RawIngestion → (parse + validate + normalize) → EmissionsDataPoint
  
If normalization fails on row 50, what do we do?
  - Return 500 error? Lose all previous work?
  - Create partial EmissionsDataPoints? Hard to track what's done.

With ParsedRecord:
  RawIngestion → (parse) → ParsedRecords ✓
  ParsedRecords → (normalize + validate) → EmissionsDataPoints
  
If normalization fails on row 50, we can:
  - Debug the specific ParsedRecord
  - Update logic and retry from row 50
  - No data loss
```

**Benefit 2: Separation of Concerns**
- Parsing: Convert CSV rows to dicts (Chunk 1.3)
- Validation: Check values are correct types (Chunk 1.5)
- Normalization: Map to standard schema (Chunk 1.5)

Each layer can be tested, debugged, and updated independently.

**Benefit 3: Audit Trail**
```
We can track:
  - When file was uploaded (RawIngestion.created_at)
  - When it was parsed (ParsedRecord.created_at)
  - When it was validated (EmissionsDataPoint.created_at)
  - When analyst approved it (ReviewTask.reviewed_at)
  
Multi-layer timestamps help with compliance and debugging.
```

---

### Q2: Why delete ParsedRecords on re-parsing instead of checking for changes?

**Answer:**
**Simple is better than complex.** Here's the tradeoff:

| Approach | Behavior | Complexity |
|----------|----------|-----------|
| **Delete & recreate (chosen)** | If called twice: same result (deterministic) | Simple: delete all, create all |
| **Check for changes** | Only update changed rows | Complex: diff old vs. new |

**Example:**
```
Version 1 parsing logic:
  - Parse row with leading spaces: "  Plant A  "

Then we update parsing logic to trim:
  - Parse row with trim: "Plant A"

Option A (delete & recreate):
  - Re-parse all → new records with "Plant A" ✓

Option B (check for changes):
  - Compare old "  Plant A  " vs. new "Plant A"
  - They're different, so update the record ✓
  - But what if they're the same? Skip ✓
  - Complex logic, more bug-prone

For MVP: Option A (simple delete & recreate) is better.

Audit trail (AuditLog) handles the "what happened" story:
  - Analyst can see: "ParsedRecord updated: spaces removed"
```

---

### Q3: What defines an "empty row"? Why those rules?

**Answer:**
Our definition:
```python
def is_row_empty(row_dict):
    # All fields are None, "", or whitespace-only
    return all(not v or (isinstance(v, str) and not v.strip()) 
               for v in row_dict.values())
```

**Examples:**

| Row | Empty? | Why |
|-----|--------|-----|
| `{"Plant": "A", "Scope": "100"}` | ❌ No | Has non-empty data |
| `{"Plant": "", "Scope": ""}` | ✅ Yes | All fields empty |
| `{"Plant": "   ", "Scope": ""}` | ✅ Yes | Whitespace doesn't count |
| `{"Plant": None, "Scope": ""}` | ✅ Yes | None doesn't count |
| `{"Plant": "A", "Scope": ""}` | ❌ No | Has one non-empty field |

**Why This Definition?**
- CSV with blank rows (user hits Enter multiple times) → all None or ""
- Common in real files (especially Excel exports)
- Fail-safe: don't create a record with no useful data
- Transparent: logged and counted in summary

**Edge Case: Intentional Null Values?**
```
What if the CSV is:
  Plant_Name,Scope2_mtCO2e
  Plant A,
```

This row has Plant A but Scope2 is empty. Should we parse it?

**Answer: Yes!**
- Plant A is non-empty → row is not empty
- Create ParsedRecord with {"Plant_Name": "Plant A", "Scope2_mtCO2e": ""}
- Later, normalization (Chunk 1.5) validates: "Scope2_mtCO2e is required" → error

This way, we preserve the data and catch the error at the right layer.

---

### Q4: Why use `enumerate(..., start=1)` for row numbering?

**Answer:**
**User-friendly**: Row numbers start at 1, matching Excel/user expectations.

```python
# enumerate(iterable, start=0) → row_num 0, 1, 2, ... (programmer view)
# enumerate(iterable, start=1) → row_num 1, 2, 3, ... (user view)

for row_num, row_data in enumerate(raw_content, start=1):
    # Row 1 is first data row
    # Row 2 is second data row
    # Matches what user sees in Excel (row 1, row 2, etc.)
```

**Note:** Header row is not included (csv.DictReader skips it).

**So:**
```csv
Plant_Name,Scope1,Year   <- Header (skipped)
Plant A,1000,2023        <- Row 1
Plant B,2000,2023        <- Row 2
```

**In ParsedRecord:**
```
source_row_number=1 → "Plant A" row
source_row_number=2 → "Plant B" row
```

---

### Q5: What happens if raw_content is None or empty list?

**Answer:**

**Case 1: raw_content is None**
```python
raw_content = raw_ingestion.raw_content or []
# If None, use empty list
```

Result: 0 ParsedRecords created, 0 errors → summary shows "parsed 0 of 0 rows".

**Case 2: raw_content is empty list `[]`**
Same as Case 1 → "parsed 0 of 0 rows".

**This happens if:**
- User uploaded an empty file (but we check for this in Chunk 1.2)
- Bug in parsing (unlikely if Chunk 1.2 is working)

---

### Q6: Why not store parsing_errors in ParsedRecord if there are errors?

**Answer:**
We DO! But notice: **for valid rows, parsing_errors is always empty `[]`**.

**Design:**

For Chunk 1.3 (parsing):
```python
ParsedRecord.parsing_errors = []  # Always empty in Chunk 1.3
```

We don't catch errors that would populate this field. They don't exist yet.

**But in Chunk 1.5 (validation/normalization):**
```python
EmissionsDataPoint.validation_errors = [...]  # Filled here
```

**Future Enhancement (Chunk X):**
If parsing logic becomes more complex (e.g., detect malformed JSON fields, unexpected encodings), we'd fill parsing_errors:

```python
ParsedRecord.parsing_errors = [
    {"field": "Scope1", "error": "Invalid number format: 'abc'"}
]
```

For MVP: Parsing is simple → no errors at this layer.

---

### Q7: How do you handle very large CSVs (1M rows)?

**Answer:**

**Current Limitation:**
```
Synchronous parsing of 1M rows:
  ~15 minutes runtime → request will timeout (Django timeout ~30 seconds)
  → 500 Internal Server Error
```

**Solution (Chunk X - Async):**

```python
# In views.py parse() method:
from celery import shared_task

@shared_task
def parse_large_ingestion_async(ingestion_id):
    raw_ingestion = RawIngestion.objects.get(id=ingestion_id)
    parse_raw_ingestion(raw_ingestion)

# In parse() view:
if raw_ingestion.line_count > 50000:
    task_id = parse_large_ingestion_async.delay(ingestion_id)
    return Response({
        "ingestion_id": str(ingestion_id),
        "status": "parsing_in_progress",
        "task_id": task_id,
        "message": "Large file queued for parsing. Check back with task_id."
    }, status=202)  # Accepted, processing
else:
    # Current synchronous path for small files
    result = parse_raw_ingestion(raw_ingestion)
    return Response({...}, status=200)
```

**Tradeoff:**
- ✅ Handles large files without timeout
- ❌ Requires Celery + message broker (Redis)
- ✅ Async gives better UX (no hanging request)
- ❌ More infrastructure to manage

For MVP (<100k rows typical), synchronous is fine.

---

### Q8: Why is the endpoint at `/api/ingest/{id}/parse/` and not `/api/parsed-records/`?

**Answer:**
**Hierarchical URL structure reflects the data model:**

```
/api/ingest/{id}/parse/
  └─ "Parse THIS ingestion"
  └─ Action-oriented: POST = perform action
  └─ Ingestion is the subject

vs.

/api/parsed-records/
  └─ "List parsed records" (GET)
  └─ Resource-oriented: standard CRUD
  └─ ParsedRecord is the subject
```

**Why ingestion-based for parse?**
- Parsing is an **action on RawIngestion**, not a CRUD operation on ParsedRecord
- User thinks: "I want to parse this file" → POST /api/ingest/{id}/parse/
- More intuitive than "create records in bulk" → POST /api/parsed-records/

**Future (Chunk 2.1): Resource-oriented endpoints**
```
GET  /api/ingest/                    # List ingestions
GET  /api/ingest/{id}/               # Get ingestion details
GET  /api/ingest/{id}/parsed-records/ # List ParsedRecords in this ingestion
GET  /api/parsed-records/             # List all ParsedRecords (cross-tenant? No!)
```

---

### Q9: What if someone uploads a CSV, then immediately calls parse twice in parallel?

**Answer:**
**Race condition possible, but safe due to transactions.**

**Scenario:**
```
Request A: POST /api/ingest/{id}/parse/
Request B: POST /api/ingest/{id}/parse/ (same moment)
```

**What Happens:**
1. Request A reads raw_ingestion.raw_content ✓
2. Request B reads raw_ingestion.raw_content ✓ (same data)
3. Request A: `ParsedRecord.objects.filter(...).delete()` → deletes existing ✓
4. Request B: `ParsedRecord.objects.filter(...).delete()` → deletes existing (already deleted) ✓
5. Request A: Creates ParsedRecords (loop + create) ✓
6. Request B: Creates ParsedRecords (loop + create) ✓

**Result:** Both succeed, but Request B's records overwrite Request A's.

**Race condition exists** (Request A's records deleted by B), but **no data loss**:
- Both calls create the same records (idempotent)
- Final state: ParsedRecords for this ingestion exist
- Deterministic: same raw_content = same result

**If This Becomes a Problem (Future):**

```python
# Add locking (Django ORM)
from django.db import transaction

with transaction.atomic():
    # Only one process can enter this block at a time
    ParsedRecord.objects.filter(ingestion_id=raw_ingestion).delete()
    for row_num, row_data in enumerate(raw_content, start=1):
        ParsedRecord.objects.create(...)
```

For MVP: Parallelization unlikely (users upload one at a time).

---

### Q10: Why log at DEBUG vs. WARNING level?

**Answer:**
**Log levels indicate severity/importance:**

```python
logger.debug(f"Created ParsedRecord for row {row_num}")
  # Detailed info for developers, not important to operators
  # Disabled by default in production

logger.warning(f"Row {row_num}: Empty row (all fields are null)")
  # Something unexpected but not fatal, operator should know
  # Enabled by default

logger.error(f"Error parsing ingestion {pk}: {str(e)}")
  # Something failed, immediate attention needed
  # Errors sent to error tracking (Sentry, etc.)
```

**Why This Pattern?**
- **DEBUG**: "Everything is fine, but here's what happened" (dev troubleshooting)
- **WARNING**: "Something unexpected, but we handled it" (operators notice issues)
- **ERROR**: "Something broke, needs attention" (alerts/oncall)

**In Production Settings:**
```python
# settings.py (Chunk 4 - deployment)
LOGGING = {
    'loggers': {
        'breathe.ingest': {
            'level': 'INFO',  # DEBUG messages hidden
        }
    }
}
```

Result: Only WARNING and ERROR logged (less noise).

---

## Edge Cases & Gotchas

### 1. CSV with Different Column Count Per Row
```csv
Plant_Name,Scope1,Year
Plant A,1000,2023,Extra
Plant B,2000,2023
```

**csv.DictReader handles this:**
- Extra columns → ignored or stored in `None` key
- Missing columns → `None` value

**Our code:** Treats as valid, stores as-is.

### 2. CSV with Unicode Characters (€, 中文, etc.)
```csv
Plant_Name,Currency
Plant A,€1000
Plant B,¥2000
```

**Our code:** Works if file is UTF-8 encoded (validated in Chunk 1.2). ✓

### 3. Ingestion Uploaded But Never Parsed
```
POST /api/ingest/upload/ → ingestion_id created
[User never calls parse]
```

**What happens:**
- RawIngestion exists with raw_content
- No ParsedRecords created
- When parsing does happen later, it works fine (idempotent)

### 4. Very Long Cell Values (100KB per cell)
```csv
Plant_Name,Description
Plant A,"This is a very long description that is 100KB of text..."
```

**Our code:** Stores as-is in JSONB. No size limits.

**Note:** JSONB supports large objects, but database may have limits (typically GB-level).

### 5. CSV with Duplicate Column Names
```csv
Plant,Plant,Scope1
A,B,1000
```

**csv.DictReader behavior:**
- Duplicate columns → last value wins
- Result: `{"Plant": "B", "Scope1": "1000"}`

**Our code:** Treats as valid, stores combined dict.

### 6. Empty CSV (Only Header, No Data)
```csv
Plant_Name,Scope1,Year
```

**Chunk 1.2 validation:** Rejects as "CSV file is empty"

**So Chunk 1.3 never sees this case.**

---

## Summary

**Chunk 1.3 implements:**
- ✅ REST endpoint to parse RawIngestion into ParsedRecords
- ✅ Row-by-row record creation with source_row_number
- ✅ Empty row detection and graceful skipping
- ✅ Idempotent re-parsing (delete old, create new)
- ✅ Summary with parsed count and error list
- ✅ Proper logging and error handling

**Key Principles:**
1. **Store raw exactly**: No cleaning or trimming
2. **Separate concerns**: Parsing only structures data, doesn't validate
3. **Fail-safe**: Empty rows skipped with logged errors
4. **Idempotent**: Same input = same output every time
5. **Auditable**: Every step logged for debugging

**Next Chunk: 1.4 - Schema Definition & Normalization Rules**

Will define:
- What fields matter (facility_name, scope_1_emissions, etc.)
- What data types are expected
- What values are valid
- How to map CSV columns to standard fields
