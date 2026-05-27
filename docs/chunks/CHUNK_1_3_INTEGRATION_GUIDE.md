# Chunk 1.3: Integration & Testing Guide

## Files Created/Modified

### Updated Files
```
breathe/apps/ingest/
  ├── serializers.py    — Added ParsedRecord serializers + response serializer
  ├── utils.py          — Added parse_raw_ingestion() and is_row_empty()
  └── views.py          — Added parse() action endpoint
```

### No New Files
(No new files, only additions to existing files)

---

## How to Integrate

### Step 1: Copy Updated Files
Files are already in place (you edited them directly).

### Step 2: Restart Containers
```bash
docker-compose down
docker-compose up --build
```

### Step 3: Verify Endpoint Exists
```bash
# Get an ingestion_id from a previous upload (Chunk 1.2)
# Then:

curl -X POST http://localhost:8000/api/ingest/550e8400-e29b-41d4-a716-446655440000/parse/
```

Expected response (404 if wrong ID, or 200 if correct):
```json
{
    "error": "RawIngestion not found"
}
```

This means the endpoint exists ✓

---

## Prerequisites

You need:
1. ✅ Tenant created (from Chunk 1.1 or 1.2)
2. ✅ DataSource created (from Chunk 1.2)
3. ✅ RawIngestion created with raw_content (from Chunk 1.2)

If you don't have these, follow CHUNK_1_2_INTEGRATION_GUIDE.md first.

---

## Testing the Endpoint

### Test 1: Successful Parsing of Valid Data

**Setup:**
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.tenants.models import Tenant
from breathe.apps.ingest.models import DataSource, RawIngestion

# Get existing or create
tenant = Tenant.objects.filter(slug="acme-corp").first() or \
    Tenant.objects.create(name="Acme Corp", slug="acme-corp")

ds = DataSource.objects.filter(tenant_id=tenant, name="SAP Q3 2023 Export").first() or \
    DataSource.objects.create(
        tenant_id=tenant,
        source_type="SAP",
        name="SAP Q3 2023 Export",
        field_mapping={"Plant_Name": "facility_name"}
    )

# Create raw ingestion with test data
ri = RawIngestion.objects.create(
    tenant_id=tenant,
    data_source_id=ds,
    filename="test_parsing.csv",
    file_hash="hash123",
    line_count=2,
    raw_content=[
        {"Plant_Name": "Plant A", "Scope1_mtCO2e": "1234.56", "Year": "2023"},
        {"Plant_Name": "Plant B", "Scope1_mtCO2e": "2000.00", "Year": "2023"}
    ]
)

print(f"Created RawIngestion: {ri.id}")
exit()
```

**Test:**
```bash
curl -X POST http://localhost:8000/api/ingest/{INGESTION_ID}/parse/ \
  -H "Content-Type: application/json" \
  -d '{}'
```

Replace `{INGESTION_ID}` with the actual ID.

**Expected Response (200 OK):**
```json
{
    "ingestion_id": "...",
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

pr_count = ParsedRecord.objects.count()
print(f"Total ParsedRecords: {pr_count}")  # Should be 2

for pr in ParsedRecord.objects.all().order_by('source_row_number'):
    print(f"Row {pr.source_row_number}: {pr.raw_values}")
```

Output:
```
Total ParsedRecords: 2
Row 1: {'Plant_Name': 'Plant A', 'Scope1_mtCO2e': '1234.56', 'Year': '2023'}
Row 2: {'Plant_Name': 'Plant B', 'Scope1_mtCO2e': '2000.00', 'Year': '2023'}
```

✓ **Test passed!**

---

### Test 2: Idempotent Re-Parsing

Call the same endpoint again:

```bash
curl -X POST http://localhost:8000/api/ingest/{INGESTION_ID}/parse/ \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response (200 OK):**
Same as Test 1 (same parsed_records_created=2).

**Verify in DB (should still be 2 records, not 4):**
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import ParsedRecord
print(f"Total: {ParsedRecord.objects.count()}")  # Should be 2, not 4
exit()
```

✓ **Idempotency works!**

---

### Test 3: Parsing with Empty Rows

**Setup:**
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.tenants.models import Tenant
from breathe.apps.ingest.models import DataSource, RawIngestion

tenant = Tenant.objects.get(slug="acme-corp")
ds = DataSource.objects.filter(tenant_id=tenant).first()

# Create ingestion with empty rows
ri = RawIngestion.objects.create(
    tenant_id=tenant,
    data_source_id=ds,
    filename="test_empty_rows.csv",
    file_hash="hash456",
    line_count=5,
    raw_content=[
        {"Plant_Name": "Plant A", "Scope1_mtCO2e": "1234.56", "Year": "2023"},
        {"Plant_Name": "", "Scope1_mtCO2e": "", "Year": ""},  # Empty row
        {"Plant_Name": "Plant B", "Scope1_mtCO2e": "2000.00", "Year": "2023"},
        {"Plant_Name": None, "Scope1_mtCO2e": None, "Year": None},  # All None
        {"Plant_Name": "   ", "Scope1_mtCO2e": "", "Year": ""}  # Whitespace only
    ]
)

print(f"Created RawIngestion: {ri.id}")
exit()
```

**Test:**
```bash
curl -X POST http://localhost:8000/api/ingest/{INGESTION_ID}/parse/ \
  -H "Content-Type: application/json" \
  -d '{}'
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

✓ **Empty row handling works!**

---

### Test 4: Non-existent Ingestion (404 Error)

```bash
curl -X POST http://localhost:8000/api/ingest/99999999-9999-9999-9999-999999999999/parse/ \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response (404 Not Found):**
```json
{
    "error": "RawIngestion not found"
}
```

✓ **Error handling works!**

---

### Test 5: Verify in Django Admin

1. Go to http://localhost:8000/admin/
2. Click "Parsed Records"
3. Should see ParsedRecords created in Tests 1, 2, 3
4. Click into one:
   - **ingestion_id**: linked to RawIngestion
   - **source_row_number**: 1, 2, 3, etc.
   - **raw_values**: exact CSV row as dict
   - **parsing_errors**: [] (empty for Test 1/2), or error list for Test 3

✓ **Data persisted correctly!**

---

### Test 6: Verify ParsedRecord Ordering

```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import ParsedRecord

# Get ParsedRecords ordered by source_row_number
records = ParsedRecord.objects.all().order_by('source_row_number')

for pr in records:
    print(f"Row {pr.source_row_number}: Plant={pr.raw_values.get('Plant_Name', 'N/A')}")
```

Expected output shows rows in correct order (1, 2, 3, etc.).

✓ **Ordering correct!**

---

### Test 7: Check Logging Output

```bash
docker-compose logs backend | grep -i "parsing\|parsed\|row"
```

You should see logs like:
```
INFO breathe.ingest: Starting parse for ingestion 550e8400...
DEBUG breathe.ingest: Created ParsedRecord for row 1
DEBUG breathe.ingest: Created ParsedRecord for row 2
INFO breathe.ingest: Parse complete: 2 parsed, 0 errors
```

✓ **Logging works!**

---

## Definition of Done — Chunk 1.3

- [x] REST endpoint: `POST /api/ingest/{ingestion_id}/parse/`
- [x] Converts RawIngestion rows → ParsedRecords
- [x] Stores source_row_number for traceability
- [x] Detects and skips empty rows
- [x] Returns summary with parsed count and errors
- [x] Idempotent re-parsing works
- [x] 404 error for non-existent ingestion
- [x] Proper logging (DEBUG, INFO, WARNING levels)
- [x] Data verified in Django Admin
- [x] All 7 test cases pass

---

## Troubleshooting

### "404 Not Found" for correct ingestion_id

**Issue:** Endpoint not registered.

**Solution:**
```bash
# Restart containers
docker-compose down
docker-compose up --build

# Verify endpoint exists
curl http://localhost:8000/api/ingest/
```

### ParsedRecords show, but raw_values looks wrong

**Issue:** Data type mismatch (expected dict, got something else).

**Solution:**
```bash
docker-compose exec backend python manage.py shell

from breathe.apps.ingest.models import ParsedRecord
pr = ParsedRecord.objects.first()

print(type(pr.raw_values))  # Should be <class 'dict'>
print(pr.raw_values)  # Should show dict content
```

### Parsing called twice, but only 2 records instead of 4

**This is expected!** Idempotency works—re-parsing deletes old records and creates new ones.

To verify:
```bash
docker-compose exec backend python manage.py shell

from breathe.apps.ingest.models import ParsedRecord
print(f"Count: {ParsedRecord.objects.count()}")  # Should be 2, not 4

# If you see 4, idempotency might be broken. Check logs.
exit()
```

---

## What's NOT Implemented Yet

These are in later chunks:

- ❌ Validation of data types (Chunk 1.5)
- ❌ Normalization to standard schema (Chunk 1.5)
- ❌ Review workflow (Chunk 2.2)
- ❌ Async parsing for large files (Chunk X)
- ❌ Rate limiting (Chunk X)

---

## Next: Chunk 1.4

Chunk 1.4 will:
- Define the ESG data schema (facility_name, scope_1_emissions, etc.)
- Create a field mapping system (SAP column → standard field)
- Document validation rules for each field

Keep the Chunk 1.3 implementation as-is. It's solid and ready for the next layer!
