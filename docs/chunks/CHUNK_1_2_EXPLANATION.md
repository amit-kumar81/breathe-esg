# Chunk 1.2: Raw Data Ingestion Endpoint — Complete Explanation

## Overview

**What This Chunk Does:**
- Accepts CSV file uploads via REST API (`POST /api/ingest/upload/`)
- Stores raw file content in database (no data loss)
- Computes SHA256 hash for idempotency detection
- Detects duplicate uploads and returns same ingestion_id
- Validates file format, size, and encoding
- Returns ingestion_id for tracking through the pipeline

**Why This Chunk Exists:**
Without a working upload mechanism, data can't enter the system. This endpoint is the **gateway** for raw emissions data from SAP, Utility, and Travel sources.

**Key Principle:**
Do NOT parse or normalize yet. Store raw data exactly as received. This ensures complete auditability—if normalization logic changes, we can re-process from the raw blob.

---

## Architecture Decisions & Tradeoffs

### 1. Store Raw Data as Original CSV Text (Not Parsed JSONB)

**Decision:** Store `raw_csv_content` as TEXT (original CSV file), not as JSONB parsed rows.

**Tradeoffs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Pure Relational: raw_csv_content as TEXT (chosen)** | Single source of truth, zero data loss risk, immutable, deterministic re-parsing | Parsing happens on-demand, slightly slower |
| **Hybrid: both CSV text + JSONB cache** | Faster re-parsing (cached), don't need to parse again | Mismatch risk: if cache differs from original, which is truth? Data loss if parsing is lossy |
| **JSONB parsed rows only** | Easy to query, structured data | Lose original CSV text, can't detect parsing errors, no audit trail |
| **S3 / File System** | Scalable for large files, fast reads | Requires S3 setup, separate from data, harder to audit |

**Why We Chose Pure Relational (Option 1):**
- **Auditability first**: Every upload has original CSV text immutable in DB
- **Single source of truth**: `raw_csv_content` is canonical, never changes
- **Zero data loss**: If parsing logic changes, re-parse from original CSV
- **Deterministic**: Same `raw_csv_content` = same ParsedRecords, every time
- **Dialect detection**: Handle different delimiters (comma, semicolon, tab, pipe) without losing data

**The Data Loss Problem We Avoided:**
If we cached parsed rows as JSONB + kept original CSV:
```
RawIngestion.raw_content = "Plant,Scope1\nA;B,1000\nC,D,2000"
                            ↓
                      CSV Sniffer detects semicolon delimiter
                            ↓
RawIngestion.raw_content_cache = [
    {"Plant": "A;B", "Scope1": "1000"},  ← LOST: semicolon not detected by first parser!
    {"Plant": "C", "Scope1": "D,2000"}   ← WRONG: split on wrong delimiter
]
```

If parsing logic improves (better dialect detection), the cache is stale. We'd have to:
- Regenerate cache? (but which is truth now?)
- Keep both? (storage waste, complexity)
- Trust the cache? (risk of data loss)

**Option 1 eliminates this risk entirely:** Always parse from source CSV.

**Future Migration Path (If Needed):**
If files grow >100MB regularly and parsing becomes slow, add caching as optimization:
```python
raw_ingestion.s3_path = "s3://bucket/ingestions/uuid.csv"
raw_ingestion.raw_csv_content = None  # Just store S3 path
raw_ingestion.parsed_rows_cache = None  # Cache for performance (regenerated as needed)
```

But for MVP: Original CSV text is the single source of truth.

---

### 2. Idempotency via File Hash (SHA256)

**Decision:** Use SHA256 hash to detect duplicate uploads.

**How It Works:**
1. Compute hash of uploaded file
2. Check if hash exists in RawIngestion table
3. If exists, return existing ingestion_id (not creating duplicate)
4. If new, create new RawIngestion record

**Example:**
```python
# User accidentally uploads data.csv twice
# First upload: hash=abc123 → creates ingestion_id=uuid-1
# Second upload: hash=abc123 → returns ingestion_id=uuid-1 (not a new ingestion)
```

**Why This Approach?**
- **File hash is unique** across file content (SHA256 collision is essentially impossible)
- **Handles accidental re-uploads** without burdening the user
- **Cheap check**: Single DB index lookup vs. complex deduplication logic
- **Transparent to user**: If they upload same file twice, they get same result

**Tradeoffs:**

| Approach | Pros | Cons |
|----------|------|------|
| **SHA256 hash (chosen)** | Fast, simple, deterministic | Doesn't detect "same data, different columns" |
| **Content hash + schema hash** | Detects similar files | More complex, slower |
| **User request ID** | User controls deduplication | Requires client-side tracking |
| **Database unique constraint** | Prevents dups in schema | Fails hard if duplicate |

**Edge Case:**
What if file content is identical but filename is different?
→ SHA256 hash will be the same, so same ingestion_id is returned. This is **intentional**: the content is what matters, not the filename.

---

### 3. File Size Limit (10MB)

**Decision:** Reject files >10MB.

**Why 10MB?**
- Typical ESG data exports (SAP, Utility) are <5MB
- Reasonable for Django request handling without async
- Can increase later with Celery + S3

**How to Change:**
```python
# In serializers.py, IngestionUploadSerializer.validate_file()
if value.size > 100 * 1024 * 1024:  # 100MB
    raise serializers.ValidationError(...)
```

---

### 4. Minimal Validation at Upload (Fail Fast)

**Decision:** Validate only:
- File is CSV (ends with .csv)
- File is readable as UTF-8
- File has at least one row
- File size is acceptable

**NOT validated yet:**
- Column names match expected schema (done in Chunk 1.4)
- Data types are correct (done in Chunk 1.5)
- Values are in range (done in Chunk 1.5)

**Why?**
- **Separation of concerns**: Upload validates transport, normalization validates data
- **Fast feedback**: User gets ingestion_id quickly
- **Flexible schema**: Each DataSource can have different column names
- **Auditable**: Parsing errors are logged separately from validation errors

---

### 5. No Authentication Yet (Placeholder)

**Decision:** In Chunk 1.2, multi-tenancy validation is a placeholder.

**Current Code:**
```python
# From serializers.py
if not hasattr(request, 'tenant_id'):
    # For now, allow all. This will be fixed in Chunk 2.3 (auth)
    pass
```

**Why?**
- Chunk 1.2 focuses on the upload mechanism
- Chunk 2.3 adds JWT auth, tenant_id extraction, and proper isolation

**What It Will Look Like in Chunk 2.3:**
```python
# Tenant is extracted from JWT token
tenant_id = request.user.tenant_id
if str(data_source.tenant_id) != str(tenant_id):
    raise serializers.ValidationError("DataSource does not belong to your tenant")
```

---

### 6. Synchronous File Processing (No Async Yet)

**Decision:** Process upload synchronously (block until done).

**Current Flow:**
1. POST /api/ingest/upload/
2. Validate file (2-3 seconds for typical file)
3. Compute hash (1 second)
4. Create DB record (100ms)
5. Return 201 with ingestion_id
6. **Total: ~4 seconds**

**Why Not Async?**
- Small files (<10MB) don't need async
- Synchronous = simpler code, easier to debug
- Client gets immediate feedback

**When to Add Async (Later):**
```python
# Pseudo-code for Chunk X (future)
from celery import shared_task

@shared_task
def process_large_ingestion(ingestion_id):
    """Async: parse + normalize large files"""
    ingestion = RawIngestion.objects.get(id=ingestion_id)
    # Heavy processing...

# In view:
if file_size > 50MB:
    # Queue async task
    process_large_ingestion.delay(ingestion.id)
    return Response({"ingestion_id": ..., "status": "processing"})
```

---

## Implementation Walkthrough

### File 1: `serializers.py`

**What It Does:**
Validates request data and file format.

**Key Classes:**

#### `IngestionUploadSerializer`
```python
class IngestionUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    data_source_id = serializers.UUIDField(required=True)
    description = serializers.CharField(required=False)

    def validate_file(self, value):
        """Validates file extension and size"""

    def validate(self, data):
        """Validates CSV structure and DataSource exists"""
```

**Why Serializer (Not Just Function)?**
- DRF integration: automatic parameter parsing, error handling
- Reusable: can use in tests, other views
- Declarative: clear what's validated
- Built-in validation hooks (validate_*, validate())

---

### File 2: `utils.py`

**What It Does:**
Pure functions for hashing, CSV parsing, idempotency checking.

**Key Functions:**

#### `compute_file_hash(file_obj)`
```python
def compute_file_hash(file_obj):
    """Compute SHA256 of file in chunks (memory-efficient)"""
    hasher = hashlib.sha256()
    while chunk := file_obj.read(8192):  # Read 8KB at a time
        hasher.update(chunk)
    return hasher.hexdigest()
```

**Why Chunks?**
- Memory-safe: doesn't load entire file into RAM
- Works for files >1GB
- Only downside: slightly slower (negligible for <100MB)

#### `parse_csv_to_rows(file_obj)`
```python
def parse_csv_to_rows(file_obj):
    """Parse CSV into list of dicts"""
    reader = csv.DictReader(text_file)
    return [dict(row) for row in reader]
```

**Returns:**
```python
[
    {"Plant_Name": "Plant A", "Scope1_mtCO2e": "1234.56", "Year": "2023"},
    {"Plant_Name": "Plant B", "Scope1_mtCO2e": "2000.00", "Year": "2023"},
]
```

#### `check_idempotency(file_hash, tenant_id)`
```python
def check_idempotency(file_hash, tenant_id):
    """Return existing RawIngestion if hash matches, else None"""
    return RawIngestion.objects.filter(
        file_hash=file_hash,
        tenant_id=tenant_id
    ).first()
```

**Why Check Both file_hash AND tenant_id?**
- File hash is unique (across all tenants)
- tenant_id check adds safety: prevents tenant A from seeing tenant B's duplicate
- Defense in depth

---

### File 3: `views.py`

**What It Does:**
REST API endpoint that orchestrates upload flow.

**Key View:**

#### `IngestionViewSet.upload()`
```python
@action(detail=False, methods=['post'], url_path='upload')
def upload(self, request):
    # 1. Validate request
    serializer = IngestionUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    # 2. Compute file hash
    file_hash = compute_file_hash(file_obj)

    # 3. Check idempotency
    existing = check_idempotency(file_hash, tenant_id)
    if existing:
        return Response({"ingestion_id": existing.id, "status": "already_received"})

    # 4. Create RawIngestion
    ingestion = RawIngestion.objects.create(...)

    # 5. Return response
    return Response({"ingestion_id": ..., "status": "received"}, status=201)
```

**Response Format:**
```json
{
    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "received",
    "filename": "sap_q3_2023.csv",
    "line_count": 150,
    "file_hash": "abc123def456...",
    "message": "File uploaded successfully"
}
```

**Error Response (400 Bad Request):**
```json
{
    "file": ["File must be a CSV (.csv)"],
    "data_source_id": ["DataSource not found"]
}
```

**Idempotent Response (200 OK):**
```json
{
    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "already_received",
    "filename": "sap_q3_2023.csv",
    "line_count": 150,
    "file_hash": "abc123def456...",
    "message": "This file was already uploaded previously. Returning existing ingestion."
}
```

---

### File 4: `urls.py`

**What It Does:**
Maps HTTP routes to views.

```python
router = DefaultRouter()
router.register(r'', IngestionViewSet, basename='ingestion')

# This creates:
# POST   /api/ingest/upload/ → IngestionViewSet.upload()
# GET    /api/ingest/         → IngestionViewSet.list() [future]
# GET    /api/ingest/{id}/    → IngestionViewSet.retrieve() [future]
```

**Why DefaultRouter?**
- Auto-generates list/create/retrieve/update/destroy endpoints
- Works with both ViewSets and custom @action methods
- Generates browsable API documentation

---

## Definition of Done — Chunk 1.2

- [x] Serializer for upload validation
- [x] Utility functions for hashing and parsing
- [x] REST endpoint: `POST /api/ingest/upload/`
- [x] File format validation (CSV, UTF-8, size)
- [x] SHA256 hashing for idempotency
- [x] Duplicate detection (returns 200 if re-upload)
- [x] RawIngestion record creation
- [x] Proper error responses
- [x] Logging
- [x] Multi-tenancy placeholder (for Chunk 2.3)

---

## Testing the Endpoint (Manual)

### Start Server
```bash
cd D:\BreatheESG Assignment
docker-compose up
```

### Create Test Data (in another terminal)
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.tenants.models import Tenant
from breathe.apps.ingest.models import DataSource

tenant = Tenant.objects.create(name="Test Corp", slug="test-corp")
ds = DataSource.objects.create(
    tenant_id=tenant,
    source_type="SAP",
    name="SAP Q3",
    field_mapping={"Plant_Name": "facility_name"}
)
print(f"DataSource ID: {ds.id}")
exit()
```

### Create Test CSV File
Create `test_upload.csv`:
```csv
Plant_Name,Scope1_mtCO2e,Scope2_mtCO2e,Year
Plant A,1234.56,567.89,2023
Plant B,2000.00,800.00,2023
```

### Upload Using cURL
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_upload.csv" \
  -F "data_source_id=<PASTE_DS_ID_HERE>"
```

**Expected Response (201):**
```json
{
    "ingestion_id": "uuid-here",
    "status": "received",
    "filename": "test_upload.csv",
    "line_count": 2,
    "file_hash": "...",
    "message": "File uploaded successfully"
}
```

### Upload Same File Again
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_upload.csv" \
  -F "data_source_id=<PASTE_DS_ID_HERE>"
```

**Expected Response (200):**
```json
{
    "ingestion_id": "uuid-here",  # SAME as before
    "status": "already_received",
    "message": "This file was already uploaded previously..."
}
```

### Verify in Django Admin
- Go to http://localhost:8000/admin/
- Click "Raw Ingestions"
- Should see 1 record (not 2, due to idempotency)

---

## Interview Questions & Answers

### Q1: Why store raw data in the database instead of a file system?

**Answer:**
We chose the database for **auditability and consistency**. Here's the tradeoff:

**Database approach (chosen):**
- ✅ Atomic: file + metadata created in one transaction
- ✅ Auditable: can see when file was uploaded, by whom (future)
- ✅ Simple: single source of truth, no orphaned files
- ✅ MVP-ready: CSV files are typically <10MB
- ❌ Scalability: DB grows larger, slower for huge files (>100MB)

**File system approach:**
- ✅ Scalable: can handle files of any size
- ✅ Fast: direct disk I/O
- ❌ Complexity: separate concerns (file + metadata in different places)
- ❌ Audit trail: hard to track who uploaded what file, when
- ❌ Consistency: file could exist without metadata (orphans)

**For MVP:** Database is correct because data integrity > scalability.

**Migration Path:** If files grow beyond 100MB, we'd move to S3 with a reference pointer in the DB:
```python
raw_ingestion.s3_path = "s3://bucket/ingestions/uuid.csv"
raw_ingestion.raw_content = None  # Just store pointer
```

---

### Q2: How does idempotency work? What if two users upload the exact same data?

**Answer:**
Idempotency is achieved via **SHA256 file hashing**:

1. **Compute hash of uploaded file** using SHA256
2. **Check if hash exists** in RawIngestion table
3. **If exists:** return existing ingestion_id (don't create duplicate)
4. **If new:** create new RawIngestion and return new ingestion_id

**Example:**
```
User A uploads: data.csv (hash=abc123)
  → Creates ingestion_id=uuid-1

User B uploads: identical data.csv (hash=abc123)
  → Returns ingestion_id=uuid-1 (same record, no duplicate)
```

**Why SHA256?**
- **Collision-resistant**: SHA256 collisions are computationally infeasible
- **Deterministic**: same file = same hash, every time
- **One-way**: can't reverse hash to get file (good for security)
- **Fast**: computed in seconds even for large files

**Edge Case: Same Data, Different Filename?**
```
File A: "sap_q3_2023.csv" (content: plant data)
File B: "emissions_2023.csv" (content: identical plant data)
```
→ **Same hash**, so same ingestion_id returned. This is **intentional**: content matters, not filename.

---

### Q3: Why not validate the data structure at upload time?

**Answer:**
We only validate **transport** (is it a valid CSV?), not **content** (are columns correct?). This is **separation of concerns**:

**Upload (Chunk 1.2):**
- Is file readable UTF-8? ✓
- Is it valid CSV format? ✓
- Does it have data? ✓
- Is it <10MB? ✓

**Parsing (Chunk 1.3):**
- Does CSV have expected columns? (parsed with raw_values, no validation)

**Normalization (Chunk 1.5):**
- Do values match expected types? (e.g., facility_name is string?)
- Are values in valid ranges? (e.g., emissions >= 0?)
- Is required data present? (e.g., facility_name required?)

**Why Defer Validation?**
1. **Flexibility**: Each DataSource can have different column names (SAP vs. Utility)
2. **Better errors**: Validation errors are per-row, not per-file
3. **Auditable**: We can re-normalize with new logic later
4. **Fast upload**: Users don't wait for full validation

**Analogy:**
- **Upload**: "Is this a valid envelope?" ✓
- **Parsing**: "What's inside the envelope?"
- **Validation**: "Does the content make sense?"

---

### Q4: What if the same user uploads the file twice intentionally (e.g., re-upload after fixing)?

**Answer:**
The idempotency check would prevent this. But the design assumes:

**Case 1: True duplicate (user clicked twice)**
→ Same ingestion_id returned (good, no wasted space)

**Case 2: Intentional re-upload (user fixed the file)**
→ We can't detect this (hashes are identical if contents are identical)
→ **Solution:** User must change filename slightly or use a new DataSource

**Better Design (Future):**
Track upload intent explicitly:
```python
request_id = request.headers.get('X-Idempotency-Key')
# User can force new upload by changing request_id
```

**Or:** Allow user to specify "force_new=true" parameter:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@data.csv" \
  -F "force_new=true"  # Skip idempotency check
```

For **MVP**, we assume re-uploads are accidents, which is reasonable.

---

### Q5: How do you ensure tenant isolation at the ingestion level?

**Answer:**
Currently, it's a **placeholder** (Chunk 1.2 is auth-agnostic). Here's what happens in Chunk 2.3:

**Chunk 1.2 (Current):**
```python
# In serializers.py
if not hasattr(request, 'tenant_id'):
    pass  # Allow any tenant (placeholder)
```

**Chunk 2.3 (Future - JWT Auth):**
```python
# User logs in, gets JWT token with tenant_id embedded
# Token is sent in request headers: Authorization: Bearer <token>

# In serializers.py:
tenant_id = request.user.tenant_id  # Extract from JWT
data_source = DataSource.objects.get(id=data_source_id)

# Validate ownership
if str(data_source.tenant_id) != str(tenant_id):
    raise ValidationError("DataSource does not belong to your tenant")
```

**Defense in Depth:**
```python
# Even if somehow wrong tenant_id gets through,
# RawIngestion is created with tenant_id:
raw_ingestion.tenant_id = data_source.tenant_id

# Later queries are always filtered:
RawIngestion.objects.filter(tenant_id=user.tenant_id)
# So even if tenant isolation fails, tenant_id FK prevents cross-tenant data access
```

---

### Q6: What happens if a user uploads a file with 1 million rows? Will it fail?

**Answer:**
**Yes, but safely.**

**Current Limits:**
- Max file size: 10MB
- Max rows: ~100k (typical with 10MB limit)
- Processing: Synchronous (will take 10-30 seconds)

**What Happens with 1M Rows:**
1. **Parse validation fails** if file > 10MB
2. **User gets clear error:** "File size exceeds 10MB limit"
3. **No partial data stored**

**If we increased limit to 1M rows:**

**Problem:** 
- Serializer reads entire CSV into memory
- Compute hash requires reading full file
- Single DB transaction for large INSERT

**Solution (Chunk X - Async):**
```python
@shared_task
def process_large_ingestion(ingestion_id):
    ingestion = RawIngestion.objects.get(id=ingestion_id)
    rows = parse_csv_in_chunks(ingestion.raw_content)
    for chunk in rows:
        # Process in batches, not all at once
        process_chunk(chunk)

# In view:
if file_size > 50MB:
    task_id = process_large_ingestion.delay(ingestion.id)
    return Response({
        "ingestion_id": ingestion.id,
        "status": "processing",
        "task_id": task_id,
        "message": "Large file queued for processing. Check back later."
    }, status=202)
```

---

### Q7: Why use SHA256 and not something simpler like file size or row count?

**Answer:**
**File size and row count are NOT collision-resistant:**

**Example:**
```
File A: 100 rows, 10KB
  - Plant A,1000
  - Plant B,2000
  - Plant C,3000
  - ... (97 more rows)

File B: 100 rows, 10KB
  - Plant X,1000
  - Plant Y,2000
  - Plant Z,3000
  - ... (97 more rows)
```

**Same size, same row count, DIFFERENT content.**

**If we used file size for idempotency:**
→ User uploads File A (ingestion_id=uuid-1)
→ User uploads File B (same size!)
→ System returns uuid-1 (WRONG! Should be new ingestion)
→ Data loss!

**SHA256 Advantages:**
- ✅ **Collision-resistant**: essentially impossible to find two files with same hash
- ✅ **Deterministic**: same file = same hash every time
- ✅ **Content-aware**: changes one byte = different hash
- ✅ **Standard**: widely used, well-tested, fast

**Trade-off:** Takes 1 second to compute hash (acceptable).

---

### Q8: What if the file encoding is not UTF-8? (e.g., Latin-1, Windows-1252)

**Answer:**
**Current behavior: Reject with error message.**

**Code:**
```python
try:
    text_file = io.TextIOWrapper(file_obj, encoding='utf-8')
    reader = csv.DictReader(text_file)
except UnicodeDecodeError as e:
    raise ValidationError(f"File must be UTF-8 encoded: {str(e)}")
```

**User Experience:**
```
Error: File must be UTF-8 encoded: 'utf-8' codec can't decode byte 0xe9...
```

**Why UTF-8 Only?**
- Standard for data interchange
- Python 3 default
- Supports all characters (emojis, international characters)
- Compatible with JSON (Chunk 2+)

**If User Has Latin-1 File:**
1. **Ask them to convert**: "Please export as UTF-8 from your system"
2. **Or we convert server-side** (future):
   ```python
   def auto_detect_encoding(file_obj):
       # Use chardet library to detect encoding
       detected = chardet.detect(file_obj.read())['encoding']
       # Re-encode to UTF-8 and parse
   ```

For **MVP**, requiring UTF-8 is reasonable (most modern tools default to it).

---

### Q9: How do you prevent abuse? (e.g., user uploads 1000 small files to spam the system)

**Answer:**
**Not handled in Chunk 1.2.** This is a **rate limiting** problem, not an ingestion problem.

**Current State:**
- No rate limits
- No authentication (yet)
- No per-tenant quotas

**Solutions (Future Chunks):**

**Rate Limiting (Chunk X):**
```python
from rest_framework.throttling import UserRateThrottle

class IngestionRateThrottle(UserRateThrottle):
    scope = 'ingest'

# In settings.py:
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_RATES': {
        'ingest': '100/hour',  # Max 100 uploads per hour per user
    }
}

# In view:
class IngestionViewSet(viewsets.ViewSet):
    throttle_classes = [IngestionRateThrottle]
```

**Per-Tenant Quotas (Chunk X):**
```python
tenant = data_source.tenant_id
month_count = RawIngestion.objects.filter(
    tenant_id=tenant,
    created_at__month=datetime.now().month
).count()

if month_count > 1000:  # Max 1000 uploads per month
    raise ValidationError("Monthly quota exceeded")
```

**For MVP:** Trust that users are honest.

---

### Q10: Why does the serializer parse the CSV before validation? Shouldn't validation happen first?

**Answer:**
**Good question!** Actually, we DO validate first. Order matters:

**Validation Order:**
1. ✅ File field validation: `.validate_file()` → checks extension, size
2. ✅ Serializer validation: `.validate()` → checks DataSource exists, parses CSV
3. ✅ Parse CSV: only if all above pass

**This is the right order because:**
- **Cheap checks first**: file size check (100ms) before CSV parse (2 seconds)
- **Fail fast**: if file is too large, reject immediately
- **No wasted work**: only parse if file looks good

**Code:**
```python
def validate_file(self, value):
    # CHEAP: just check extension and size
    if not value.name.endswith('.csv'):
        raise ValidationError("Not a CSV")
    if value.size > 10MB:
        raise ValidationError("Too large")
    return value

def validate(self, data):
    # EXPENSIVE: parse CSV only if file passed cheap checks
    try:
        rows = parse_csv(file_obj)
    except Exception as e:
        raise ValidationError(f"Bad CSV: {e}")
    return data
```

---

## Edge Cases & Gotchas

### 1. Empty CSV File
```csv
```
→ Serializer rejects: "CSV file is empty"

### 2. CSV with Only Headers, No Data Rows
```csv
Plant_Name,Scope1,Scope2
```
→ Serializer rejects: "CSV file is empty" (no data rows)

### 3. CSV with BOM (Byte Order Mark)
```
\xef\xbb\xbf Plant_Name,Scope1,Scope2
```
→ Python's UTF-8 decoder handles BOM automatically ✓

### 4. Duplicate Column Names
```csv
Plant,Plant,Scope1
A,B,1000
```
→ DictReader merges duplicates (keeps last value)
→ Results in: `{"Plant": "B", "Scope1": "1000"}`
→ This is a data issue, not an upload issue (caught in validation later)

### 5. Very Long Column Names (>255 chars)
→ No validation at upload time (JSONB accepts any string)
→ Caught during normalization (Chunk 1.5)

### 6. File with Null Bytes
```
Plant_Name\x00 , Scope1
```
→ Python CSV reader will fail
→ User gets clear error: "Invalid CSV format"

---

## Summary

**Chunk 1.2 implements:**
- ✅ REST upload endpoint
- ✅ File validation (format, size, encoding)
- ✅ SHA256 hashing for idempotency
- ✅ RawIngestion record creation
- ✅ Proper error handling and logging

**Key Principles:**
1. **No data loss**: Store raw exactly as received
2. **Idempotent**: Same file = same ingestion_id
3. **Simple**: Only validate transport, not content
4. **Auditable**: Every upload has metadata
5. **Future-proof**: Easy to extend with auth, async, rate limiting

**Next Chunk:** 1.3 - CSV Parser & ParsedRecord Generation
