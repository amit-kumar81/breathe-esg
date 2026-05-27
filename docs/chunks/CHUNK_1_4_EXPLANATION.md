# Chunk 1.4: Schema Definition & Normalization Rules — Complete Explanation

## Overview

**What This Chunk Does:**
- Defines standard fields for emissions data (facility_name, scope_1/2/3_emissions, reporting_year, data_quality_score)
- Maps CSV columns (DataSource.field_mapping) to standard fields
- Validates each field (required, type, range, format)
- Creates NormalizedRecord for each ParsedRecord with validation results
- Calculates data quality scores (0-100)
- Enables row-level traceability and audit trail

**Why This Chunk Exists:**
Data from different sources (SAP, Utility, Travel) uses different column names. We need a **single standard schema** for:
- Consistent querying across sources
- Validation before analyst review
- Audit trail (which rows are valid, which have errors)
- Automated approval workflows (valid rows auto-approved, invalid rows queued for analyst)

**Key Principle:**
Normalization is **deterministic and repeatable**. If validation logic changes, re-normalize from same ParsedRecords and get same result.

---

## Architecture Decisions & Tradeoffs

### 1. Define Standard Fields (Not Schema-Less)

**Decision:** Define a fixed set of standard fields instead of accepting arbitrary JSON.

**Standard Fields:**
```
facility_name (string, required)
scope_1_emissions (decimal, optional)
scope_2_emissions (decimal, optional)
scope_3_emissions (decimal, optional)
reporting_year (int, required)
data_quality_score (0-100, optional)
```

**Tradeoffs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Fixed schema (chosen)** | Consistent, queryable, easy to aggregate | Less flexible, must update schema for new fields |
| **Schema-less JSONB** | Flexible, accepts any structure | Hard to query, validate, aggregate across tenants |
| **Hybrid (fields + JSONB)** | Flexibility + structure | Complex, harder to maintain |

**Why Fixed Schema:**
- **Queryable**: Can do `SELECT facility_name, scope_1_emissions WHERE scope_1_emissions > 1000`
- **Aggregable**: Can sum emissions by facility, by year, by scope
- **Comparable**: Different tenants use same fields (standardization goal)
- **Indexable**: Fast filtering on facility_name, year, etc.

**Evolution Path:**
If we need new fields (e.g., biogenic_emissions, methodology):
```sql
ALTER TABLE ingest_normalized_record ADD COLUMN biogenic_emissions DECIMAL(15,4);
```

Not a big deal. Schema evolution is manageable in PostgreSQL.

---

### 2. Field Mapping (CSV Columns → Standard Fields)

**Decision:** Store field_mapping in DataSource model, apply during normalization.

**Example - SAP Export:**
```python
DataSource.field_mapping = {
    "Plant_Name": "facility_name",
    "Scope1_mtCO2e": "scope_1_emissions",
    "Scope2_mtCO2e": "scope_2_emissions",
    "Year": "reporting_year"
}
```

**Process:**
1. ParsedRecord.raw_values: `{"Plant_Name": "Plant A", "Scope1_mtCO2e": "1234.56", ...}`
2. Apply mapping: `facility_name="Plant A", scope_1_emissions="1234.56"`
3. Validate: facility_name is non-empty ✓, scope_1_emissions is numeric ✓
4. Create NormalizedRecord with validated values

**Tradeoffs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Field mapping in DataSource (chosen)** | Flexible, per-source customization, stored in DB | Requires admin to configure |
| **Hard-coded mapping** | Simple, no config needed | Not flexible, must code for each source |
| **Auto-detect columns** | No config needed | Error-prone, assumes column names |
| **User specifies at upload** | Transparent | Bad UX, user must know their file structure |

**Why DataSource Mapping:**
- Different sources have different column names
- Admin configures once, then all uploads use it
- Easy to test (mock DataSource with different mappings)
- Documented in DB (audit trail)

---

### 3. Validation Rules (Required, Type, Range)

**Decision:** Define validation rules per field, enforce during normalization.

**Rules:**

```python
facility_name:
  - required: True
  - type: string
  - max_length: 255
  - validates: not empty, not all whitespace

scope_1_emissions:
  - required: False
  - type: Decimal
  - min: 0 (non-negative)
  - max: 15 digits, 4 decimal places
  - validates: numeric, non-negative, not NaN/Infinity

scope_2_emissions:
  - required: False
  - same as scope_1_emissions

scope_3_emissions:
  - required: False
  - same as scope_1_emissions

reporting_year:
  - required: True
  - type: int
  - min: 1900
  - max: 2100
  - validates: numeric, in range

data_quality_score:
  - required: False
  - type: int
  - min: 0
  - max: 100
  - default: 0
```

**Tradeoffs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Strict validation (chosen)** | Catches errors early, prevents bad data | Rejects edge cases, requires user to fix |
| **Lenient validation** | Accepts more data, fewer rejections | Bad data enters system, harder to audit |
| **No validation** | Fastest, no errors | No quality control, garbage data |

**Why Strict:**
- ESG data must be accurate (used for compliance, sustainability claims)
- Early rejection is better than late discovery (analysis stage)
- Validation errors are logged, user can see what's wrong

---

### 4. Data Quality Score Calculation

**Decision:** Auto-calculate quality score (0-100) based on completeness and validation.

**Scoring Logic:**
```
Start at 100
-10 points for each validation error (facility_name missing, emissions invalid, etc.)
-5 points for each missing optional field (scope_2, scope_3)
Floor at 0

Example:
- facility_name present, year valid: 100 (perfect)
- facility_name missing: 90
- facility_name missing + scope_2 missing: 80
- facility_name missing + scope_2 missing + scope_3 missing: 70
- facility_name missing + invalid year: 70
```

**Tradeoffs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Auto-calculated (chosen)** | Consistent, transparent, no manual work | Scoring may not match analyst judgment |
| **Manual analyst scoring** | Reflects human judgment | Not scalable, inconsistent |
| **ML-based scoring** | Could learn patterns | Overkill for MVP, hard to explain |

**Why Auto-Calculate:**
- Consistent across all records
- Transparent (scoring formula is visible)
- Enables automated workflows ("score > 80 → auto-approve")
- Can be adjusted later (change formula in code)

---

### 5. NormalizedRecord vs. EmissionsDataPoint

**Decision:** Create separate NormalizedRecord (validated but not approved) and EmissionsDataPoint (approved by analyst).

**Data Flow:**
```
RawIngestion (original CSV text)
    ↓ [Chunk 1.3: Parse]
ParsedRecord (structured dict, no validation)
    ↓ [Chunk 1.4: Normalize + Validate]
NormalizedRecord (validated, but not approved)
    ↓ [Chunk 1.5: Analyst Review & Approval]
EmissionsDataPoint (approved, ready for analytics)
```

**Why Separate Models?**

| Layer | Purpose | Example |
|-------|---------|---------|
| ParsedRecord | Preserve structure | raw_values: {"Plant": "A", "Scope1": "1234.56"} |
| NormalizedRecord | Preserve validation state | facility_name="A", scope_1_emissions=1234.56, is_valid=True |
| EmissionsDataPoint | Preserve approval state | approved_by=analyst_user, reviewed_at=2023-11-15 |

**Benefits:**
- **Audit trail**: Can trace from raw CSV → normalized → approved
- **Retry logic**: If normalization fails, fix and re-normalize (NormalizedRecord deleted, recreated)
- **Analyst workflow**: See which records passed validation, which need review
- **Rollback**: If approver makes mistake, just delete EmissionsDataPoint, NormalizedRecord still exists

---

## Implementation Walkthrough

### File 1: `validators.py` (New)

**Purpose:** Pure validation functions, no DB access.

**Key Functions:**

#### `validate_facility_name(value, required=True)`
```python
def validate_facility_name(value, required=True):
    """Returns (is_valid: bool, normalized: str, error_msg: str)"""
    
    # Trim whitespace
    value_str = str(value).strip()
    
    # Check required
    if not value_str and required:
        return False, None, "Facility name is required"
    
    # Check length
    if len(value_str) > 255:
        return False, None, "Facility name exceeds 255 characters"
    
    return True, value_str, None
```

**Why Return Tuple?**
- Multiple values (validity, result, error) in one call
- Chainable: can collect all errors before creating record
- Testable: pure function, no side effects

#### `validate_emissions_value(value, allow_zero=True, allow_negative=False)`
```python
def validate_emissions_value(value, allow_zero=True, allow_negative=False):
    """Converts to Decimal, checks range, returns validated value"""
    
    try:
        decimal_value = Decimal(str(value).strip())
    except InvalidOperation:
        return False, None, f"Invalid number format: '{value}'"
    
    if not allow_negative and decimal_value < 0:
        return False, None, "Emissions must be non-negative"
    
    if not allow_zero and decimal_value == 0:
        return False, None, "Emissions must be greater than zero"
    
    return True, decimal_value, None
```

**Why Decimal Instead of Float?**
- Float: 1.234567890123456 → precision loss
- Decimal: exact decimal representation, required for financial/ESG data
- Database: DecimalField(max_digits=15, decimal_places=4) expects Decimal

---

### File 2: `normalization.py` (New)

**Purpose:** Pure normalization logic (no DB writes), orchestrates validation.

**Key Function:**

#### `normalize_parsed_record(parsed_record, data_source)`

**Process:**
```python
def normalize_parsed_record(parsed_record, data_source):
    raw_values = parsed_record.raw_values  # {"Plant_Name": "A", "Scope1": "1234"}
    field_mapping = data_source.field_mapping  # {"Plant_Name": "facility_name", ...}
    
    normalized_values = {}
    validation_errors = []
    
    # For each CSV column → standard field mapping
    for csv_column, standard_field in field_mapping.items():
        raw_value = raw_values.get(csv_column)
        
        # Validate the value
        is_valid, norm_val, error_msg = validate_field_value(
            standard_field, raw_value, STANDARD_FIELDS[standard_field]
        )
        
        if is_valid:
            normalized_values[standard_field] = norm_val
        else:
            validation_errors.append({
                "field": standard_field,
                "csv_column": csv_column,
                "error": error_msg
            })
    
    # Check for missing required fields
    for field_name, field_config in STANDARD_FIELDS.items():
        if field_config.get('required') and field_name not in normalized_values:
            validation_errors.append({"field": field_name, "error": "required field missing"})
    
    # Calculate quality score
    data_quality_score = calculate_data_quality_score(normalized_values, validation_errors)
    is_valid = len(validation_errors) == 0
    
    return {
        "normalized_values": normalized_values,
        "validation_errors": validation_errors,
        "is_valid": is_valid,
        "data_quality_score": data_quality_score
    }
```

**Why Pure Logic (No DB)?**
- Testable: no fixtures needed
- Fast: can unit test millions of validations
- Reusable: can call from batch jobs, API, CLI
- Easy to debug: inputs → outputs, no side effects

---

### File 3: `views.py` (Updated)

**New Action: `normalize()`**

**Endpoint:** `POST /api/ingest/{ingestion_id}/normalize/`

**Flow:**
```python
def normalize(self, request, pk=None):
    # 1. Get RawIngestion
    raw_ingestion = RawIngestion.objects.get(id=pk)
    
    # 2. Check ParsedRecords exist
    parsed_count = ParsedRecord.objects.filter(ingestion_id=raw_ingestion).count()
    if parsed_count == 0:
        return 400 "No ParsedRecords found. Call /parse/ first."
    
    # 3. Call normalization logic
    result = normalize_ingestion(raw_ingestion)
    
    # 4. Return summary
    return 200 {
        "ingestion_id": ...,
        "status": "normalized",
        "total_parsed_records": ...,
        "total_normalized_records": ...,
        "valid_records_count": ...,
        "invalid_records_count": ...,
        "normalization_errors": [...]
    }
```

**Response Format (Success):**
```json
{
    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "normalized",
    "total_parsed_records": 100,
    "total_normalized_records": 100,
    "valid_records_count": 95,
    "invalid_records_count": 5,
    "normalization_errors": [],
    "message": "Successfully normalized 100 records (95 valid, 5 invalid)"
}
```

**Response Format (With Errors):**
```json
{
    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "normalized",
    "total_parsed_records": 100,
    "total_normalized_records": 99,
    "valid_records_count": 95,
    "invalid_records_count": 4,
    "normalization_errors": [
        {
            "row_number": 50,
            "error": "Error normalizing row 50: ..."
        }
    ],
    "message": "Successfully normalized 99 records (95 valid, 4 invalid)"
}
```

---

### File 4: `serializers.py` (Updated)

**New Serializers:**

#### `NormalizationResponseSerializer`
Documents the response shape for API clients.

#### `NormalizedRecordListSerializer`
For `GET /api/ingest/{id}/normalized-records/` (future).

#### `NormalizedRecordDetailSerializer`
For `GET /api/ingest/{id}/normalized-records/{record_id}/` (future).

---

### File 5: `models.py` (Updated)

**New Model: `NormalizedRecord`**

```python
class NormalizedRecord(models.Model):
    # Relational fields (indexed for fast querying)
    facility_name = CharField(max_length=255, db_index=True)
    scope_1_emissions = DecimalField(...)
    scope_2_emissions = DecimalField(...)
    scope_3_emissions = DecimalField(...)
    reporting_year = IntegerField(db_index=True)
    data_quality_score = IntegerField(default=0)
    
    # JSONB fields (flexible, full audit trail)
    normalized_values = JSONField()  # Complete normalized dict
    validation_errors = JSONField()  # List of validation errors
    data_quality_flags = JSONField()  # List of quality warnings
    is_valid = BooleanField(db_index=True)  # Quick filter for valid records
```

**Why Both Relational + JSONB?**
- **Relational** (facility_name, scope_1_emissions): Fast filtering and aggregation
- **JSONB** (normalized_values): Complete audit trail, can re-validate later

---

## Definition of Done — Chunk 1.4

- [x] Define standard fields (facility_name, scope_1/2/3_emissions, year, quality_score)
- [x] Create field validators (type, required, range checks)
- [x] Create NormalizedRecord model
- [x] Implement field mapping (CSV columns → standard fields)
- [x] Create normalization logic (pure functions, testable)
- [x] Implement normalize endpoint
- [x] Calculate data quality scores (0-100)
- [x] Create NormalizedRecord with validation results
- [x] Idempotent re-normalization (delete old, create new)
- [x] Proper error handling and logging
- [x] Multi-tenancy support (tenant_id on model)

---

## Interview Questions & Answers

### Q1: Why use a fixed schema instead of schema-less JSON?

**Answer:**
Schema-less (pure JSONB) is flexible but creates problems:

```python
# Schema-less approach
NormalizedRecord.data = {
    "facility_name": "Plant A",
    "scope_1_emissions": 1234.56,
    "scope_2_emissions": None,
    "custom_field_xyz": "whatever"  # One tenant adds this
}

# Problem: Can we query scope_1_emissions > 1000?
SELECT * FROM normalized_records
WHERE data ->> 'scope_1_emissions' > 1000::numeric
# This is slow (not indexed), error-prone (type coercion)

# How do we aggregate across tenants?
SELECT tenant_id, SUM(data ->> 'scope_1_emissions')
# Converts JSONB to numeric, slow, not cached
```

**Fixed schema (chosen):**
```python
# Relational approach
NormalizedRecord.facility_name = "Plant A"
NormalizedRecord.scope_1_emissions = Decimal("1234.56")

# Query is fast and indexed
SELECT * FROM normalized_records
WHERE scope_1_emissions > 1000
# Uses index, returns in milliseconds

# Aggregation is fast
SELECT tenant_id, SUM(scope_1_emissions)
FROM normalized_records
GROUP BY tenant_id
# Single pass, leverages column statistics
```

**Trade-off:**
- ✅ Fixed schema: queryable, aggregable, fast
- ❌ Fixed schema: must update schema for new fields
- ✅ JSONB: flexible, no schema updates
- ❌ JSONB: slow queries, can't index, can't aggregate well

**For MVP (standardized emissions data):** Fixed schema is correct. If we need custom per-tenant fields later (unlikely), we'd add a separate `custom_values` JSONB column.

---

### Q2: What if a DataSource doesn't have all fields (e.g., only scope_1, not scope_2)?

**Answer:**
That's fine! Scope 2 and 3 are optional.

**Example - Utility Company Data:**
```python
DataSource.field_mapping = {
    "FacilityName": "facility_name",
    "ElectricityMWh": "scope_2_emissions",  # Only scope 2, no scope 1 or 3
    "YearReported": "reporting_year"
}

# Parsed record
ParsedRecord.raw_values = {
    "FacilityName": "Office Building",
    "ElectricityMWh": "5000",
    "YearReported": "2023"
}

# Normalized record
NormalizedRecord:
  facility_name = "Office Building"
  scope_1_emissions = None  (optional, not provided)
  scope_2_emissions = 5000.0  (required for this source)
  scope_3_emissions = None  (optional, not provided)
  reporting_year = 2023
  is_valid = True  (all required fields present)

# Data quality score
Score = 100 - 5 (missing scope_1) - 5 (missing scope_3) = 90
```

**Key Point:**
Validation checks:
1. Is facility_name present? → Required ✓
2. Is reporting_year present? → Required ✓
3. Is scope_1_emissions present? → Optional ✓ (None is OK)
4. Is scope_2_emissions present? → Optional ✓ (None is OK)

**Result:** is_valid = True, data_quality_score = 90 (due to missing optional fields)

---

### Q3: What happens if field_mapping has unmapped CSV columns?

**Answer:**
Unmapped columns are **ignored** (logged as warning).

**Example:**
```python
DataSource.field_mapping = {
    "Plant_Name": "facility_name",
    "Scope1": "scope_1_emissions",
    "Year": "reporting_year"
}

ParsedRecord.raw_values = {
    "Plant_Name": "A",
    "Scope1": "1234",
    "Year": "2023",
    "InternalID": "12345",  # Not in field_mapping!
    "Comments": "...",      # Not in field_mapping!
}

# Normalization process
for csv_col, standard_field in field_mapping.items():
    # Processes: Plant_Name, Scope1, Year
    # Ignores: InternalID, Comments

# Result
logger.debug("CSV column 'InternalID' not in field_mapping (ignored)")
logger.debug("CSV column 'Comments' not in field_mapping (ignored)")

NormalizedRecord:
  facility_name = "A"
  scope_1_emissions = 1234.0
  reporting_year = 2023
  # InternalID and Comments are NOT stored (not in standard schema)
```

**Trade-off:**
- ✅ Flexible: CSV can have extra columns (no error)
- ❌ Silent failure: If admin forgets to map a column, it's silently ignored

**Mitigation:**
Log unmapped columns at DEBUG level. Analyst can check logs: "Column 'InternalID' was not mapped, values were lost."

---

### Q4: What if the same CSV column maps to multiple standard fields?

**Answer:**
**Not supported.** field_mapping is a one-way mapping (one CSV column → one standard field).

**Invalid Example:**
```python
# WRONG: Don't do this
DataSource.field_mapping = {
    "Emissions": "scope_1_emissions",
    "Emissions": "scope_2_emissions",  # Can't map same column twice!
}
```

**Solution:** Admin must choose which field it maps to, or split into two columns before upload.

```python
# CORRECT: Choose one
DataSource.field_mapping = {
    "Scope1_Emissions": "scope_1_emissions",
    "Scope2_Emissions": "scope_2_emissions",
}
```

**Future Enhancement (Chunk X):**
If we need multi-column normalization (e.g., "Emissions + Unit → scope_1_emissions"):
```python
# Advanced field mapping (not in MVP)
DataSource.field_mapping = {
    "Emissions": {
        "type": "number",
        "target": "scope_1_emissions",
        "unit_column": "Unit",  # Get unit from "Unit" column
        "convert_to": "mtCO2e"  # Convert to standard unit
    }
}
```

For MVP: Simple 1-to-1 mapping is sufficient.

---

### Q5: How do you handle CSV files with inconsistent number of columns?

**Answer:**
CSV parsing handles this (done in Chunk 1.3), normalization expects consistent ParsedRecords.

**Example - CSV with Missing Columns:**
```csv
Plant_Name,Scope1,Scope2,Year
Plant A,1000,500,2023
Plant B,1500,,2023          <- Missing Scope2 (empty cell)
Plant C,2000,800,2023
```

**In Chunk 1.3 (Parse):**
```python
# csv.DictReader with dialect detection
ParsedRecord for row 2:
  raw_values = {
    "Plant_Name": "Plant B",
    "Scope1": "1500",
    "Scope2": "",           # Empty string for missing cell
    "Year": "2023"
  }
```

**In Chunk 1.4 (Normalize):**
```python
field_mapping = {
    "Plant_Name": "facility_name",
    "Scope1": "scope_1_emissions",
    "Scope2": "scope_2_emissions",
    "Year": "reporting_year"
}

# Validate each field
validate_facility_name("Plant B") → (True, "Plant B", None)
validate_emissions_value("1500") → (True, Decimal("1500"), None)
validate_emissions_value("") → (False, None, "empty string for optional field")  # If scope_2 is optional, this is skipped
validate_reporting_year("2023") → (True, 2023, None)

# Result
NormalizedRecord:
  facility_name = "Plant B"
  scope_1_emissions = 1500.0
  scope_2_emissions = None  (optional, empty cell OK)
  reporting_year = 2023
  is_valid = True
```

**Key Design:**
- Empty cells in CSV → empty strings in raw_values
- Validators treat empty strings gracefully (required vs. optional)
- Optional fields: empty is OK, added to normalized_values as None
- Required fields: empty is error, added to validation_errors

---

### Q6: What if validation logic changes (e.g., change min_year from 1900 to 2000)?

**Answer:**
**Re-normalize from existing ParsedRecords.**

**Scenario:**
```
Chunk 1.4 v1.0:
  MIN_YEAR = 1900
  
User uploads data with Year=1950 → is_valid=True

Later: Chunk 1.4 v2.0:
  MIN_YEAR = 2000 (new requirement: only modern data)
  
Need to re-normalize...
```

**Process:**
1. Update validators.py: `MIN_YEAR = 2000`
2. Call normalize endpoint again: `POST /api/ingest/{id}/normalize/`
3. Normalization logic deletes old NormalizedRecords
4. Re-runs normalization with new rules
5. Year=1950 now fails validation: "Year out of range (2000-2100)"

**Result:**
```
Old NormalizedRecord:
  reporting_year = 1950
  is_valid = True
  (deleted)

New NormalizedRecord:
  reporting_year = 1950
  is_valid = False
  validation_errors = [{"field": "reporting_year", "error": "Year out of range"}]
```

**Benefits:**
- ✅ Idempotent: can re-normalize safely
- ✅ Deterministic: same ParsedRecords → same result
- ✅ No data loss: ParsedRecords (raw CSV) unchanged
- ✅ Audit trail: old state lost, but can see in AuditLog

**Note:** This is why we store ParsedRecords (raw CSV rows) separately. Can always re-normalize.

---

### Q7: How do you prevent analyst from working on invalid records?

**Answer:**
**Filter by is_valid flag in next stages.**

**Chunk 1.5 (Analyst Review) will:**
```python
# List records waiting for review
NormalizedRecord.objects.filter(
    ingestion_id=...,
    is_valid=False  # Only show invalid records (need analyst attention)
)

# Auto-approve valid records (optional workflow enhancement)
NormalizedRecord.objects.filter(
    ingestion_id=...,
    is_valid=True,
    data_quality_score__gte=80  # Valid AND high quality
).update(approved=True)
```

**Workflow Example:**
```
1. Analyst uploads CSV → ParsedRecords created
2. API calls normalize → NormalizedRecords created
3. Analyst sees dashboard:
   - 95 valid records (green) → Ready for approval
   - 5 invalid records (red) → Needs review
4. Analyst clicks invalid record:
   - Sees raw_values from CSV
   - Sees validation_errors
   - Can edit CSV and re-upload (or we add edit UI later)
5. Once all valid, analyst approves batch → EmissionsDataPoints created
```

---

### Q8: What if a field validation fails partway through record processing?

**Answer:**
**Continue processing, collect all errors, report in summary.**

**Example - Record with Multiple Errors:**
```python
raw_values = {
    "Plant_Name": "",           # Empty!
    "Scope1": "abc",            # Not a number!
    "Scope2": "1234",
    "Year": "1800"              # Year out of range!
}

# Validation process
validate_facility_name("") → Error: "required field missing"
validate_emissions_value("abc") → Error: "Invalid number format"
validate_emissions_value("1234") → (True, 1234.0, None)
validate_reporting_year("1800") → Error: "Year out of range (1900-2100)"

# Collect all errors
validation_errors = [
    {"field": "facility_name", "error": "required field missing"},
    {"field": "scope_1_emissions", "error": "Invalid number format"},
    {"field": "reporting_year", "error": "Year out of range (1900-2100)"}
]

# Don't stop at first error! Continue and collect all.
NormalizedRecord:
  facility_name = None
  scope_1_emissions = None
  scope_2_emissions = 1234.0
  reporting_year = None
  is_valid = False
  validation_errors = [... all 3 errors ...]
  data_quality_score = 100 - 30 = 70
```

**Why Continue?**
- Analyst sees all problems at once (not just first error)
- Better UX (analyst doesn't have to fix one, re-upload, fix another)
- Batch efficiency (process entire file, return summary)

---

### Q9: How do you handle edge cases like "  100  " (spaces around number)?

**Answer:**
**Trim spaces during validation.**

```python
def validate_emissions_value(value):
    value_str = str(value).strip()  # Trim spaces!
    decimal_value = Decimal(value_str)
    return True, decimal_value, None

# Example
validate_emissions_value("  1234.56  ") → (True, Decimal("1234.56"), None)
```

**Why Trim?**
- Common CSV export error (Excel adds spaces)
- Expected behavior (trim is implicit in most data processing)
- Don't lose data to whitespace

---

### Q10: What if data_quality_score calculation doesn't match analyst judgment?

**Answer:**
**Score is a hint, not the law. Analyst can override.**

```
Scenario:
  NormalizedRecord has:
    scope_1_emissions = 1234.56
    scope_2_emissions = None (missing optional)
    scope_3_emissions = None (missing optional)
    is_valid = True
    data_quality_score = 90

  Analyst says: "Scope 2 is actually unknown (not missing).
                 This is a complete record. Score should be 100!"
```

**Solutions (Future):**
1. Add note/comment field: "Analyst override: score should be 100 because..."
2. In Chunk 1.5, analyst can adjust score before approval
3. Adjust calculation: scope_2/3 only count as missing if marked as required-for-this-source

For MVP: Score is informational, analyst decides approval.

---

## Edge Cases & Gotchas

### 1. CSV with BOM (Byte Order Mark)
```
Raw file: \xef\xbb\xbf facility_name,scope1,year
```
✅ Python UTF-8 decoder handles BOM automatically.

### 2. Duplicate Column Names in CSV
```csv
Plant,Plant,Scope1
A,B,1000
```
→ csv.DictReader merges: `{"Plant": "B", "Scope1": "1000"}`
→ Data loss: first "A" is overwritten.
→ Not our problem (Chunk 1.3 parse issue), but logged.

### 3. Field Mapping References Non-Existent CSV Column
```python
field_mapping = {
    "PlantName": "facility_name",
    "NonExistent": "scope_1_emissions"  # CSV doesn't have this!
}
```
→ raw_values.get("NonExistent") → None
→ Validation fails: "scope_1_emissions is required" (if it's required)
→ Caught during normalization.

### 4. Decimal Precision Loss
```python
# CSV value: "1234567890.1234567"
validate_emissions_value("1234567890.1234567")
# Database: DecimalField(max_digits=15, decimal_places=4)
# Stores: 1234567890.1235 (rounded!)
```
→ Precision loss, but logged in validation.
→ Better than silent loss (float would silently corrupt).

---

## Summary

**Chunk 1.4 implements:**
- ✅ Standard field definitions (facility_name, scope_1/2/3_emissions, year, quality_score)
- ✅ Field validators (required, type, range checks)
- ✅ NormalizedRecord model (with relational + JSONB design)
- ✅ Field mapping (CSV columns → standard fields)
- ✅ Normalization endpoint: `POST /api/ingest/{id}/normalize/`
- ✅ Data quality score calculation (0-100, based on completeness)
- ✅ Validation error tracking (per-record, detailed)
- ✅ Idempotent re-normalization
- ✅ Proper logging and error handling

**Key Principles:**
1. **Fixed schema for consistency**: Not schema-less, enables fast querying
2. **Separate validation concerns**: Parse (Chunk 1.3) → Normalize (Chunk 1.4) → Approve (Chunk 1.5)
3. **Error isolation**: Collect all validation errors, don't stop at first
4. **Deterministic**: Same ParsedRecords = same NormalizedRecords (can re-normalize safely)
5. **Transparent scoring**: Data quality score is calculated, not subjective

**Next Chunk:** 1.5 - Analyst Review & Approval (Chunk 1.5 will create EmissionsDataPoints from valid NormalizedRecords)
