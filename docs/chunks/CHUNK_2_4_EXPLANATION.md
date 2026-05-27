# Chunk 2.4: Ingestion Workflow Endpoints - Detailed Explanation

## Overview

Chunk 2.4 implements the **Ingestion Workflow API** that orchestrates the complete pipeline from CSV upload to analyst review. Users upload a file and progress through four steps: upload → parse → normalize → complete. Each step is idempotent (safe to re-run) and provides detailed progress feedback.

---

## Architecture Decision 1: Step-Based Workflow vs. Single-Click Upload

### The Decision
We implement a **4-step workflow** (upload → parse → normalize → complete) rather than a single "upload and process" endpoint.

```python
# ✅ Step-based (Chunk 2.4):
POST /api/ingest/upload/ → step 1 (save file)
POST /api/ingest/{id}/parse/ → step 2 (parse rows)
POST /api/ingest/{id}/normalize/ → step 3 (validate)
GET /api/ingest/{id}/status/ → check progress

# ❌ NOT single-click:
POST /api/ingest/upload/ → all 4 steps happen, return when done
```

### Why This Decision

**Visibility and Control**: Each step is explicit. If parsing fails, the user knows exactly where the failure happened. With single-click, the user waits and gets "Upload failed" with no context.

**Debugging**: Data providers can stop after parsing to see which rows have parsing errors. They can fix the CSV and re-parse without re-uploading the file.

**Idempotency**: Each step is independently idempotent. If step 2 (parsing) succeeds but step 3 (normalization) fails, the user can fix validation logic and re-run step 3 without re-parsing.

**Progress Feedback**: Each step takes different amounts of time:
- Upload: <1s (just store file)
- Parse: 1-5s (read CSV, build dict per row)
- Normalize: 5-30s (apply logic, validate, score)

Breaking into steps lets the UI show progress bars and ETA.

### Alternative Considered: Single-Click Upload
```python
@action(detail=False, methods=['post'])
def upload(self, request):
    # All in one:
    # 1. Save file
    # 2. Parse
    # 3. Normalize
    # 4. Create review tasks
    # Return when all done
```

**Why Rejected**: If parsing fails on row 50,000 of 100,000 rows:
- With steps: User sees "Parse 50% complete, error on row 50000, try again"
- With single-click: User waits 2 minutes, gets "Failed" with no context

Step-based is better for large files.

---

## Architecture Decision 2: Idempotent Operations (Safe Re-Running)

### The Decision
Each step (parse, normalize) can be re-run without creating duplicates. Re-running deletes old records and creates new ones with updated logic.

```python
# First parse:
POST /api/ingest/{id}/parse/ → Creates ParsedRecords

# If validation logic is updated, re-run parse:
POST /api/ingest/{id}/parse/ → Deletes old ParsedRecords, creates new ones

# No duplicates, no orphaned records
```

### Why This Decision

**Error Recovery**: If a bug is found in parsing logic, fix it and re-parse the same file. No need to re-upload.

**Schema Changes**: If the normalized field mapping changes, re-normalize existing files with new logic.

**Testing**: During development, upload a file once, then run parse/normalize repeatedly while testing.

### Implementation Detail
```python
# In parse() action:
ParsedRecord.objects.filter(ingestion_id=ingestion.id).delete()
# Parse fresh
```

This ensures:
- No orphaned records from previous runs
- Each re-run is a clean slate
- Deterministic (same input → same output)

### Alternative Considered: Append-Only
```python
# Never delete, just create new records with a version number
class ParsedRecord(models.Model):
    ingestion_id = FK
    version = IntegerField(default=1)  # Incremented on each parse

# Problems:
# - Queries must always filter by version=latest
# - Old versions clutter the database
# - Deletion/cleanup needed eventually
```

**Why Rejected**: Complexity with little benefit. Idempotent replace is simpler.

---

## Architecture Decision 3: Synchronous Processing (No Celery for MVP)

### The Decision
All processing (upload, parse, normalize) is synchronous. The endpoint waits for completion and returns the result. No background jobs, no Celery queue.

```python
# Synchronous:
POST /api/ingest/{id}/parse/
→ Parses all rows (might take 5-30s)
→ Returns status

# NOT async:
POST /api/ingest/{id}/parse/
→ Queues parsing job
→ Returns 202 Accepted immediately
→ User polls GET /api/ingest/{id}/status/ to check progress
```

### Why This Decision

**Simplicity**: No Celery, Redis, or worker processes. Everything runs in the request/response cycle.

**MVP Timeline**: Reduces operational complexity. Easier to debug. Easier to test.

**File Size Limits**: For reasonable file sizes (10k-100k rows), parsing takes <30 seconds, which is acceptable for HTTP timeouts (usually 60-300s).

**Determinism**: Synchronous ensures consistent behavior. No timing issues with background jobs.

### When to Add Async
Files >500k rows, parsing takes >60s:
- Add Celery
- POST /api/ingest/parse/ returns 202 Accepted
- User polls GET /api/ingest/status/ or WebSocket for updates

For MVP, synchronous is sufficient.

### Alternative Considered: Async with Celery
```python
# Requires:
# - Redis or RabbitMQ message broker
# - Celery worker processes
# - Task tracking and polling
# - More complex testing
```

**Why Deferred**: Overkill for MVP. Complexity for benefit not yet needed.

---

## Architecture Decision 4: Progress Tracking via RawIngestion Status Field

### The Decision
Progress is tracked by updating `RawIngestion.status` field: UPLOAD → PARSED → NORMALIZED → COMPLETE.

```python
class RawIngestion(models.Model):
    status = CharField(choices=[
        'UPLOAD',      # File received
        'PARSED',      # Parsed into rows
        'NORMALIZED',  # Normalized and validated
        'COMPLETE'     # Ready for review
    ])
    
    uploaded_at = DateTimeField()
    parsed_at = DateTimeField()
    normalized_at = DateTimeField()
    completed_at = DateTimeField()
```

### Why This Decision

**Queryability**: Analysts can find ingestions by status:
```python
# Show me all ingestions waiting to be normalized
RawIngestion.objects.filter(status='PARSED')
```

**Auditability**: Timestamps show when each step completed (useful for SLAs).

**State Machine**: Status forms a state machine. Rules about valid transitions enforce workflow integrity.

### Alternative Considered: Separate Progress Table
```python
class IngestionProgress(models.Model):
    ingestion = FK
    step = CharField()  # 'upload', 'parse', 'normalize'
    status = CharField()  # 'pending', 'in_progress', 'complete'
    progress_percentage = IntegerField()
```

**Why Rejected**: Overcomplication. Single status field on RawIngestion is sufficient for MVP.

---

## Architecture Decision 5: Field Mapping Applied During Normalization

### The Decision
CSV columns are mapped to standard fields using `DataSource.field_mapping` at normalization time, not parsing time.

```python
# DataSource.field_mapping:
{
  "Plant_Name": "facility_name",
  "CO2_Scope1": "scope_1_emissions",
  "Year": "reporting_year"
}

# Parsing (step 2) just extracts rows as dicts:
{
  "Plant_Name": "Plant A",
  "CO2_Scope1": "500",
  "Year": "2023"
}

# Normalization (step 3) applies mapping:
{
  "facility_name": "Plant A",
  "scope_1_emissions": 500.0,
  "reporting_year": 2023
}
```

### Why This Decision

**Separation of Concerns**: 
- Parsing: CSV format → dict (generic)
- Normalization: dict → standard schema (business logic)

**Flexibility**: Multiple data sources can have different field mappings. Parsing is agnostic; normalization applies the right mapping.

**Validation Context**: Normalization step knows which fields are required (via field_mapping). Parsing doesn't assume anything.

### Alternative Considered: Map During Parsing
```python
# Parse AND apply mapping in one step
# Problem: If mapping changes, must re-parse
# Better: Keep parse generic, apply mapping at normalization
```

**Why Rejected**: Less flexible. Re-parsing old files with new mappings would require changes to parsing logic.

---

## Architecture Decision 6: Data Quality Score Calculated Per Record

### The Decision
Each normalized record gets a data_quality_score (0-100) based on:
- Completeness: % of fields filled
- Validity: % without validation errors

```python
completeness = (filled_fields / total_fields) * 100
validity = 100 if no_errors else 0
data_quality_score = (completeness * 0.8) + (validity * 0.2)
```

### Why This Decision

**Tiered Approval**: High-quality records (score ≥80) can be auto-approved. Low-quality records require manual review.

**Prioritization**: Analysts can focus on worst records first (lowest scores).

**Metrics**: "90% of our data has quality_score ≥80" is a useful KPI.

### Alternative Considered: Binary Valid/Invalid
```python
is_valid = bool(not validation_errors)
# No spectrum, just pass/fail
```

**Why Rejected**: Loses nuance. A record with 1 missing field is different from 1 with all fields empty. Quality score captures that.

---

## Architecture Decision 7: Auto-Approval for High-Quality Records

### The Decision
Records with `is_valid=True` and `data_quality_score≥80` are automatically set to status='AUTO_APPROVED'. Analysts only review exceptions.

```python
if normalized_record.is_valid and normalized_record.data_quality_score >= 80:
    review_task.status = 'AUTO_APPROVED'
else:
    review_task.status = 'PENDING'
```

### Why This Decision

**Efficiency**: If 80% of records are auto-approved, analysts review only 20%. Scales linearly with data quality improvements.

**Accountability**: AUTO_APPROVED records still create AuditLog with action='SYSTEM_AUTO_APPROVED'. Not anonymous.

**Feedback Loop**: As data sources improve, more records are auto-approved. Clear metric of source quality.

### Alternative Considered: All Manual Review
```python
# All records stay PENDING, analysts review every one
review_task.status = 'PENDING'
```

**Why Rejected**: Bottleneck. 10k records per month, 2 analysts = 5k records each. With auto-approval, maybe only 2k manual reviews.

---

## Architecture Decision 8: Timezone-Naive Timestamps

### The Decision
RawIngestion uses `DateTimeField` with `auto_now_add=True` and `auto_now=True`. No timezone awareness for MVP.

```python
uploaded_at = DateTimeField(auto_now_add=True)  # UTC
parsed_at = DateTimeField(null=True, blank=True)
normalized_at = DateTimeField(null=True, blank=True)
```

### Why This Decision

**Simplicity**: No timezone conversions, no pytz complexity. All times in UTC.

**Auditability**: Times are consistent in logs and database.

**Production Note**: For global SaaS, switch to timezone-aware later with `USE_TZ = True`.

---

## Architecture Decision 9: Sample Records in Detail Endpoint

### The Decision
GET /api/ingest/{id}/ includes sample parsed/normalized records with errors, not full lists.

```python
{
  "sample_parsed_records": [
    {"source_row_number": 5, "raw_values": {...}, "parsing_errors": [...]},
    {"source_row_number": 10, "raw_values": {...}, "parsing_errors": [...]},
    ...  # Up to 5 samples
  ],
  "sample_normalized_records": [
    {"facility_name": "...", "validation_errors": [...]},
    ...  # Up to 5 samples
  ]
}
```

### Why This Decision

**Response Size**: Full list of 100k records would be huge. Samples show the problems without overwhelming the response.

**Actionability**: "First 5 rows with errors" is enough for data provider to spot the pattern.

**Performance**: Samples are cheap to query. Full list would require pagination and multiple requests.

### Alternative Considered: Full List with Pagination
```python
GET /api/ingest/{id}/parsed_records/
→ Paginated list of all parsed records
```

**Why Not Included Yet**: Works, but requires separate endpoint. For MVP, samples suffice.

---

## Architecture Decision 10: Multi-Tenant Isolation in Ingestion

### The Decision
All ingestion data (RawIngestion, ParsedRecord, NormalizedRecord) includes `tenant_id` foreign key. Users can only see/modify their tenant's ingestions.

```python
class RawIngestion(models.Model):
    tenant_id = ForeignKey(Tenant)  # Row-level isolation

class IngestionViewSet(TenantQuerySetMixin, ...):
    # TenantQuerySetMixin auto-filters by tenant_id
```

### Why This Decision

**Security**: User from Tenant A cannot see Tenant B's data uploads.

**Consistency**: Matches isolation in Chunk 2.3. All data is tenant-scoped.

**Compliance**: Audit logs show which tenant uploaded what, when.

---

## Summary of Design Decisions

| Decision | Why | Trade-Off |
|----------|-----|-----------|
| **Step-based workflow** | Visibility, debugging, idempotency | Slower UX (3 clicks vs 1) |
| **Idempotent operations** | Error recovery, schema updates | Must clean old records |
| **Synchronous processing** | Simplicity for MVP | Slower for huge files (>500k rows) |
| **Status field for progress** | Simple, queryable | Limited to discrete steps |
| **Field mapping at normalize** | Flexible, separates concerns | Extra step needed |
| **Data quality score** | Tiered approval, metrics | Added complexity |
| **Auto-approval logic** | Efficiency, positive feedback | Analysts don't review everything |
| **Timezone-naive times** | Simplicity for MVP | Upgrade needed for global SaaS |
| **Sample records** | Response size, performance | Not full data visibility |
| **Multi-tenant isolation** | Security, consistency | Extra FK on every model |

---

## Testing Strategy

This chunk is validated through 10+ integration tests (see INTEGRATION_GUIDE):

1. **Upload CSV**: File saved, RawIngestion created, hash computed for idempotency
2. **Idempotent Upload**: Same file twice returns same ingestion_id
3. **Parse Rows**: CSV parsed into ParsedRecords with raw_values
4. **Parse Idempotent**: Re-parse deletes old records, creates new ones
5. **Normalize Rows**: Parsed records normalized, validated, quality scored
6. **Auto-Approval**: Records with score ≥80 and is_valid=True auto-approved
7. **Status Endpoint**: Returns summary with completion percentage
8. **Detail Endpoint**: Includes sample records with errors
9. **Field Mapping**: DataSource.field_mapping applied correctly
10. **Multi-Tenant Isolation**: Users only see own tenant's ingestions
11. **Error Tracking**: Parsing and validation errors captured and queryable
12. **Progress Tracking**: Timestamps updated at each step

---

This chunk completes the data ingestion pipeline. Chunks 2.5+ build on this foundation (export, reporting, analytics).
