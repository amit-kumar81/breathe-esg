# Chunk 1.4: Schema Definition & Normalization Rules — Integration Guide

## Test Setup

### Prerequisites

Ensure you have from previous chunks:
- 1 Tenant
- 1 DataSource with field_mapping configured
- 1 RawIngestion with raw_csv_content
- ParsedRecords created from that ingestion

If not, follow CHUNK_1_2_INTEGRATION_GUIDE.md and CHUNK_1_3_INTEGRATION_GUIDE.md.

### Migration

Before testing, run Django migrations:

```bash
cd D:\BreatheESG Assignment
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate
```

This creates:
- `ingest_normalized_record` table
- Indexes on facility_name, reporting_year, is_valid

### Create Test DataSource with Field Mapping

```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.tenants.models import Tenant
from breathe.apps.ingest.models import DataSource

# Use existing tenant from Chunk 1.2
tenant = Tenant.objects.first()

# Create SAP DataSource with field mapping
sap_ds = DataSource.objects.create(
    tenant_id=tenant,
    source_type="SAP",
    name="SAP Q4 2023",
    description="SAP emissions export with Scope 1, 2, 3",
    field_mapping={
        "Plant_Name": "facility_name",
        "Scope1_mtCO2e": "scope_1_emissions",
        "Scope2_mtCO2e": "scope_2_emissions",
        "Scope3_mtCO2e": "scope_3_emissions",
        "Year": "reporting_year"
    }
)
print(f"SAP DataSource ID: {sap_ds.id}")

# Create Utility DataSource (only Scope 2)
utility_ds = DataSource.objects.create(
    tenant_id=tenant,
    source_type="UTILITY",
    name="Utility Portal 2023",
    description="Electricity usage (Scope 2 only)",
    field_mapping={
        "FacilityName": "facility_name",
        "ElectricityMWh": "scope_2_emissions",
        "ReportingYear": "reporting_year"
    }
)
print(f"Utility DataSource ID: {utility_ds.id}")

exit()
```

---

## Test Cases

### Test 1: Basic Normalization (All Valid Fields)

**Setup:**
Create CSV file `test_normalize_valid.csv`:
```csv
Plant_Name,Scope1_mtCO2e,Scope2_mtCO2e,Scope3_mtCO2e,Year
Plant A,1000.50,500.25,200.00,2023
Plant B,1500.75,600.50,300.25,2023
Plant C,2000.00,0,0,2023
```

**Steps:**

1. Upload file:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_normalize_valid.csv" \
  -F "data_source_id=<SAP_DS_ID>"
```

Expected: `200 OK` or `201 Created` with ingestion_id.
Save ingestion_id: `INGEST_ID=<value>`

2. Parse:
```bash
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID/parse/
```

Expected: `200 OK` with 3 parsed records.

3. Normalize:
```bash
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID/normalize/
```

**Expected Response (200 OK):**
```json
{
    "ingestion_id": "$INGEST_ID",
    "status": "normalized",
    "total_parsed_records": 3,
    "total_normalized_records": 3,
    "valid_records_count": 3,
    "invalid_records_count": 0,
    "normalization_errors": [],
    "message": "Successfully normalized 3 records (3 valid, 0 invalid)"
}
```

4. Verify in Django Admin:
- Go to http://localhost:8000/admin/
- Click "Normalized Records"
- Should see 3 records, all with is_valid=True
- data_quality_score should be 100 (all fields present)

5. Verify in Shell:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord

records = NormalizedRecord.objects.all()
print(f"Total: {records.count()}")  # Should be 3

for r in records:
    print(f"Row {r.parsed_record_id.source_row_number}:")
    print(f"  facility_name: {r.facility_name}")
    print(f"  scope_1_emissions: {r.scope_1_emissions}")
    print(f"  scope_2_emissions: {r.scope_2_emissions}")
    print(f"  scope_3_emissions: {r.scope_3_emissions}")
    print(f"  reporting_year: {r.reporting_year}")
    print(f"  is_valid: {r.is_valid}")
    print(f"  data_quality_score: {r.data_quality_score}")
    print(f"  validation_errors: {r.validation_errors}")
    print()

exit()
```

---

### Test 2: Normalization with Missing Optional Fields

**Setup:**
Create CSV file `test_normalize_partial.csv`:
```csv
Plant_Name,Scope1_mtCO2e,Year
Plant A,1000.50,2023
Plant B,1500.75,2023
```

Note: Scope2 and Scope3 are missing.

**Steps:**

1. Upload:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_normalize_partial.csv" \
  -F "data_source_id=<SAP_DS_ID>"
```

Save ingestion_id as `INGEST_ID2`.

2. Parse:
```bash
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID2/parse/
```

3. Normalize:
```bash
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID2/normalize/
```

**Expected Response:**
```json
{
    "ingestion_id": "$INGEST_ID2",
    "status": "normalized",
    "total_parsed_records": 2,
    "total_normalized_records": 2,
    "valid_records_count": 2,
    "invalid_records_count": 0,
    "normalization_errors": [],
    "message": "Successfully normalized 2 records (2 valid, 0 invalid)"
}
```

4. Verify Quality Score:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord

records = NormalizedRecord.objects.filter(
    parsed_record_id__ingestion_id__id__in=['$INGEST_ID2']
)

for r in records:
    print(f"{r.facility_name}: score={r.data_quality_score}")
    # Expected: 90 (missing scope_2 -5, missing scope_3 -5)
    # 100 - 5 - 5 = 90
```

---

### Test 3: Normalization with Validation Errors

**Setup:**
Create CSV file `test_normalize_invalid.csv`:
```csv
Plant_Name,Scope1_mtCO2e,Scope2_mtCO2e,Year
,1000,500,2023
Plant B,abc,600,2023
Plant C,2000,800,1850
Plant D,2000,800,2023
```

Expected errors:
- Row 1: Missing facility_name (required)
- Row 2: scope_1_emissions "abc" (not numeric)
- Row 3: Year 1850 (out of range 1900-2100)
- Row 4: Valid ✓

**Steps:**

1. Upload:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_normalize_invalid.csv" \
  -F "data_source_id=<SAP_DS_ID>"
```

Save as `INGEST_ID3`.

2. Parse and Normalize:
```bash
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID3/parse/
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID3/normalize/
```

**Expected Response:**
```json
{
    "ingestion_id": "$INGEST_ID3",
    "status": "normalized",
    "total_parsed_records": 4,
    "total_normalized_records": 4,
    "valid_records_count": 1,
    "invalid_records_count": 3,
    "normalization_errors": [],
    "message": "Successfully normalized 4 records (1 valid, 3 invalid)"
}
```

3. Verify Validation Errors:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord
import json

records = NormalizedRecord.objects.all().order_by('parsed_record_id__source_row_number')

for r in records:
    print(f"\nRow {r.parsed_record_id.source_row_number}:")
    print(f"  is_valid: {r.is_valid}")
    print(f"  data_quality_score: {r.data_quality_score}")
    print(f"  validation_errors:")
    for err in r.validation_errors:
        print(f"    - {err['field']}: {err['error']}")

# Expected output:
# Row 1:
#   is_valid: False
#   data_quality_score: 80  (100 - 10 error - 5 missing scope2 - 5 missing scope3)
#   validation_errors:
#     - facility_name: Facility name is required

# Row 2:
#   is_valid: False
#   data_quality_score: 80
#   validation_errors:
#     - scope_1_emissions: Invalid number format: 'abc'

# Row 3:
#   is_valid: False
#   data_quality_score: 80
#   validation_errors:
#     - reporting_year: Year out of range (1900-2100), got 1850

# Row 4:
#   is_valid: True
#   data_quality_score: 100

exit()
```

---

### Test 4: Different DataSource (Utility, Only Scope 2)

**Setup:**
Create CSV file `test_normalize_utility.csv`:
```csv
FacilityName,ElectricityMWh,ReportingYear
Office Tower,5000,2023
Factory,12000,2023
```

Using Utility DataSource (only scope_2_emissions):

**Steps:**

1. Upload:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_normalize_utility.csv" \
  -F "data_source_id=<UTILITY_DS_ID>"
```

Save as `INGEST_ID4`.

2. Parse and Normalize:
```bash
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID4/parse/
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID4/normalize/
```

3. Verify:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord

records = NormalizedRecord.objects.all().order_by('-created_at')[:2]

for r in records:
    print(f"{r.facility_name}:")
    print(f"  scope_1_emissions: {r.scope_1_emissions}")  # Should be None
    print(f"  scope_2_emissions: {r.scope_2_emissions}")  # Should have value
    print(f"  scope_3_emissions: {r.scope_3_emissions}")  # Should be None
    print(f"  data_quality_score: {r.data_quality_score}")  # Should be ~90 (missing optional scopes)
```

---

### Test 5: Idempotent Re-Normalization

**Setup:**
Use INGEST_ID from Test 1.

**Steps:**

1. Check initial count:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord

initial_count = NormalizedRecord.objects.count()
print(f"Initial NormalizedRecords: {initial_count}")
```

2. Call normalize endpoint again:
```bash
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID/normalize/
```

Expected: Same response as first call (same counts, same errors).

3. Verify no duplication:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord

final_count = NormalizedRecord.objects.count()
print(f"Final NormalizedRecords: {final_count}")
print(f"Match initial? {initial_count == final_count}")
# Expected: True (no new records created, old ones deleted and recreated)
```

---

### Test 6: Spaces Around Numbers (Edge Case)

**Setup:**
Create CSV file `test_normalize_spaces.csv`:
```csv
Plant_Name,Scope1_mtCO2e,Year
  Plant A  ,  1000.50  ,  2023  
Plant B,1500.75,2023
```

Note: Extra spaces around values.

**Steps:**

1. Upload, Parse, Normalize:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_normalize_spaces.csv" \
  -F "data_source_id=<SAP_DS_ID>"
# Save INGEST_ID5

curl -X POST http://localhost:8000/api/ingest/$INGEST_ID5/parse/
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID5/normalize/
```

2. Verify Trimming:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord

records = NormalizedRecord.objects.all().order_by('-created_at')[:2]

for r in records:
    print(f"facility_name: '{r.facility_name}'")  # Should be "Plant A", not "  Plant A  "
    print(f"scope_1_emissions: {r.scope_1_emissions}")  # Should be Decimal('1000.50'), not string
```

---

### Test 7: Non-Existent Ingestion (404 Error)

**Steps:**

```bash
curl -X POST http://localhost:8000/api/ingest/99999999-9999-9999-9999-999999999999/normalize/
```

**Expected Response (404 Not Found):**
```json
{
    "error": "RawIngestion not found"
}
```

---

### Test 8: Normalize Without ParsedRecords (Bad Request)

**Setup:**
Create a RawIngestion but don't call /parse/ first.

```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.tenants.models import Tenant
from breathe.apps.ingest.models import DataSource, RawIngestion

tenant = Tenant.objects.first()
ds = DataSource.objects.first()

# Create RawIngestion but no ParsedRecords
ingestion = RawIngestion.objects.create(
    tenant_id=tenant,
    data_source_id=ds,
    filename="test.csv",
    file_hash="dummy_hash_123",
    line_count=2,
    raw_csv_content="Plant,Scope1\nA,1000\nB,2000"
)
print(f"Ingestion ID: {ingestion.id}")
exit()
```

**Steps:**

Call normalize without parse:
```bash
curl -X POST http://localhost:8000/api/ingest/$INGESTION_ID/normalize/
```

**Expected Response (400 Bad Request):**
```json
{
    "error": "No ParsedRecords found. Call /parse/ first."
}
```

---

### Test 9: Data Quality Score Calculation

**Setup:**
Create CSV with different field completeness:

```csv
Plant_Name,Scope1_mtCO2e,Scope2_mtCO2e,Scope3_mtCO2e,Year
Full Record,1000,500,300,2023
Partial Scope,1000,500,,2023
Only Scope1,1000,,,2023
Only Facility,,,,,2023
```

**Steps:**

1. Upload, Parse, Normalize:
```bash
# (upload/parse/normalize steps)
```

2. Check Scores:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord

records = NormalizedRecord.objects.all().order_by('-created_at')[:4]

for r in records:
    print(f"{r.facility_name}: score={r.data_quality_score}")

# Expected:
# Full Record: 100 (all fields)
# Partial Scope: 95 (missing scope3 -5)
# Only Scope1: 90 (missing scope2 -5, scope3 -5)
# Only Facility: Invalid (missing required year field)
```

---

### Test 10: Mixed Valid and Invalid in Single Batch

**Setup:**
Create CSV with mix of valid and invalid:

```csv
Plant_Name,Scope1_mtCO2e,Year
Plant A,1000,2023
,2000,2023
Plant C,3000,2025
```

Expected: 1 valid, 2 invalid.

**Steps:**

1. Full workflow:
```bash
curl -X POST http://localhost:8000/api/ingest/upload/ \
  -F "file=@test_mixed.csv" \
  -F "data_source_id=<SAP_DS_ID>"
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID/parse/
curl -X POST http://localhost:8000/api/ingest/$INGEST_ID/normalize/
```

2. Verify Summary:
```json
{
    "total_parsed_records": 3,
    "total_normalized_records": 3,
    "valid_records_count": 1,
    "invalid_records_count": 2
}
```

3. Check Details:
```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.ingest.models import NormalizedRecord

records = NormalizedRecord.objects.all().order_by('-created_at')[:3]

valid_count = sum(1 for r in records if r.is_valid)
invalid_count = sum(1 for r in records if not r.is_valid)

print(f"Valid: {valid_count}, Invalid: {invalid_count}")

for r in records:
    status = "✓" if r.is_valid else "✗"
    print(f"{status} {r.facility_name}: {len(r.validation_errors)} errors")
```

---

## Summary

**Coverage:**
- ✅ Test 1: Basic normalization (all valid fields)
- ✅ Test 2: Partial fields (optional fields missing)
- ✅ Test 3: Validation errors (required field missing, invalid type, out of range)
- ✅ Test 4: Different DataSource mapping (Utility vs. SAP)
- ✅ Test 5: Idempotent re-normalization (no duplication)
- ✅ Test 6: Edge cases (spaces around numbers)
- ✅ Test 7: Error handling (404, 400)
- ✅ Test 8: Dependency validation (must parse before normalize)
- ✅ Test 9: Data quality score (correct calculations)
- ✅ Test 10: Mixed valid/invalid batch

**All tests passing means:**
- ✅ Normalization logic is correct
- ✅ Field mapping works for different DataSources
- ✅ Validators catch errors properly
- ✅ Data quality scores are accurate
- ✅ Idempotency works
- ✅ Edge cases handled gracefully
