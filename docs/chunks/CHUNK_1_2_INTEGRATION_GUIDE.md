# Chunk 1.2: Integration & Testing Guide

## Files Created/Modified

### New Files
```
breathe/apps/ingest/
  ├── serializers.py      # DRF serializers for upload validation
  ├── utils.py            # Utility functions (hashing, parsing, idempotency)
  └── views.py            # REST endpoint for upload
```

### Modified Files
```
breathe/apps/ingest/
  └── urls.py             # Added router for IngestionViewSet
```

### Documentation
```
CHUNK_1_2_EXPLANATION.md      # Complete architecture & interview Q&A
CHUNK_1_2_INTEGRATION_GUIDE.md # This file
```

---

## How to Integrate

### Step 1: Copy Files
Files are already in place. No additional copying needed.

### Step 2: Update requirements.txt (if needed)
The `dj_database_url` and `gunicorn` from Chunk 1.1 already support this chunk.

No new Python dependencies needed.

### Step 3: Restart Containers
```bash
docker-compose down
docker-compose up --build
```

The new view should be automatically picked up.

### Step 4: Verify Endpoint Exists
```bash
curl http://localhost:8000/api/ingest/upload/
```

Expected response (405 Method Not Allowed, because GET is not supported):
```json
{
    "detail": "Method \"GET\" not allowed. Expected one of: POST."
}
```

This confirms the endpoint exists! ✓

---

## Testing the Endpoint

### Prerequisite: Create Test Data

```bash
docker-compose exec backend python manage.py shell
```

In Python shell:
```python
from breathe.apps.tenants.models import Tenant
from breathe.apps.ingest.models import DataSource

# Create tenant
tenant = Tenant.objects.create(name="Acme Corp", slug="acme-corp")

# Create data source
ds = DataSource.objects.create(
    tenant_id=tenant,
    source_type="SAP",
    name="SAP Q3 2023 Export",
    field_mapping={
        "Plant_Name": "facility_name",
        "Scope1_mtCO2e": "scope_1_emissions",
        "Year": "year"
    }
)

print(f"Tenant ID: {tenant.id}")
print(f"DataSource ID: {ds.id}")

exit()
```

**Note down the DataSource ID.**

### Test 1: Successful Upload

Create `test_data.csv`:
```csv
Plant_Name,Scope1_mtCO2e,Scope2_mtCO2e,Year
Plant A,1234.56,567.89,2023
Plant B,2000.00,800.00,2023
```

Upload:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_data.csv" \
  -F "data_source_id=<PASTE_DS_ID_HERE>"
```

**Expected Response (201 Created):**
```json
{
    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "received",
    "filename": "test_data.csv",
    "line_count": 2,
    "file_hash": "abc123def456...",
    "message": "File uploaded successfully"
}
```

**Note the ingestion_id for next test.**

### Test 2: Idempotency (Re-upload Same File)

Upload the **exact same file** again:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_data.csv" \
  -F "data_source_id=<PASTE_DS_ID_HERE>"
```

**Expected Response (200 OK, not 201):**
```json
{
    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",  # SAME as before!
    "status": "already_received",
    "filename": "test_data.csv",
    "line_count": 2,
    "file_hash": "abc123def456...",
    "message": "This file was already uploaded previously. Returning existing ingestion."
}
```

**Verify in DB:**
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import RawIngestion

count = RawIngestion.objects.count()
print(f"Total RawIngestions: {count}")  # Should be 1, not 2!
```

✓ **Idempotency works!**

### Test 3: Invalid File (Not CSV)

Create `test_data.txt`:
```
Just some text
Not a CSV file
```

Upload:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_data.txt" \
  -F "data_source_id=<PASTE_DS_ID_HERE>"
```

**Expected Response (400 Bad Request):**
```json
{
    "file": ["File must be a CSV (.csv)"]
}
```

✓ **File validation works!**

### Test 4: Invalid DataSource ID

```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_data.csv" \
  -F "data_source_id=99999999-9999-9999-9999-999999999999"
```

**Expected Response (400 Bad Request):**
```json
{
    "non_field_errors": ["DataSource not found"]
}
```

✓ **DataSource validation works!**

### Test 5: Empty CSV File

Create `empty.csv`:
```csv
```

Upload:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@empty.csv" \
  -F "data_source_id=<PASTE_DS_ID_HERE>"
```

**Expected Response (400 Bad Request):**
```json
{
    "non_field_errors": ["CSV file is empty"]
}
```

✓ **Empty file validation works!**

### Test 6: Very Large File (>10MB)

This test verifies the file size limit.

```bash
# Create a 15MB test file
dd if=/dev/zero of=large_file.csv bs=1M count=15

# Try to upload
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@large_file.csv" \
  -F "data_source_id=<PASTE_DS_ID_HERE>"
```

**Expected Response (400 Bad Request):**
```json
{
    "file": ["File size exceeds 10MB limit"]
}
```

✓ **Size limit works!**

### Test 7: Verify in Django Admin

1. Go to http://localhost:8000/admin/
2. Click "Raw Ingestions"
3. Should see 1 record (from Test 1 and 2, idempotent)
4. Click into it:
   - Filename: `test_data.csv`
   - Line count: `2`
   - Raw content: List of 2 dicts
   ```json
   [
       {"Plant_Name": "Plant A", "Scope1_mtCO2e": "1234.56", ...},
       {"Plant_Name": "Plant B", "Scope1_mtCO2e": "2000.00", ...}
   ]
   ```

✓ **Raw ingestion stored correctly!**

---

## Definition of Done — Chunk 1.2

- [x] Serializer validates file (format, size, encoding)
- [x] Serializer validates DataSource exists
- [x] Utility functions for hashing and CSV parsing
- [x] View endpoint: `POST /api/ingest/upload/`
- [x] Idempotency via SHA256 hash
- [x] RawIngestion record created
- [x] Error responses are clear (400, 404, etc.)
- [x] Logging implemented
- [x] All manual tests pass
- [x] Comprehensive documentation (explanation + Q&A)

---

## Accessing Logs

To see what's happening behind the scenes:

```bash
docker-compose logs backend
```

You should see:
```
INFO breathe.ingest: File hash: abc123def456...
INFO breathe.ingest: Created RawIngestion: <uuid>
```

---

## What's NOT Implemented Yet

These are handled in later chunks:

- ❌ Authentication (Chunk 2.3)
- ❌ Per-tenant filtering (Chunk 2.3)
- ❌ Async processing for large files (Chunk X)
- ❌ Rate limiting (Chunk X)
- ❌ CSV parsing into ParsedRecords (Chunk 1.3)
- ❌ Validation and normalization (Chunks 1.4-1.5)

---

## Troubleshooting

### "404 Not Found" when accessing `/api/ingest/upload/`

**Issue:** The URL isn't registered.

**Solution:** 
```bash
# Restart containers
docker-compose down
docker-compose up --build

# Verify in Django shell:
docker-compose exec backend python manage.py shell
from django.urls import reverse
print(reverse('ingestion:upload'))
```

### "file_hash must be unique" error when uploading

**Issue:** File already uploaded with same hash but something went wrong.

**Solution:**
```bash
# Check existing records
docker-compose exec backend python manage.py shell

from breathe.apps.ingest.models import RawIngestion
RawIngestion.objects.all().delete()  # Clear test data

exit()
```

### File uploaded but not showing in admin

**Issue:** Page not refreshed or record in another tenant.

**Solution:**
```bash
# Check if record exists
docker-compose exec backend python manage.py shell

from breathe.apps.ingest.models import RawIngestion
for ri in RawIngestion.objects.all():
    print(f"{ri.id}: {ri.filename} ({ri.line_count} rows)")

exit()
```

---

## Next: Chunk 1.3

Chunk 1.3 will:
- Create a `POST /api/ingest/{id}/parse/` endpoint
- Convert RawIngestion rows → ParsedRecords
- Handle parsing errors per-row
- Return summary of parsed records

Keep the Chunk 1.2 implementation as-is. It's the foundation for everything that follows!
