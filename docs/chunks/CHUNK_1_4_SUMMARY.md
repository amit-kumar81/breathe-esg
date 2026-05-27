# Chunk 1.4: Schema Definition & Normalization Rules — Summary

## What Was Built

**Chunk 1.4** completes the ingest pipeline by adding the normalization layer that converts raw parsed CSV data into validated, standardized records.

### Core Components

1. **Standard Field Definitions** (validators.py)
   - facility_name (string, required)
   - scope_1/2/3_emissions (Decimal, optional)
   - reporting_year (int, required)
   - data_quality_score (0-100, auto-calculated)

2. **Validation Layer** (validators.py)
   - `validate_facility_name()`: String, required, max 255 chars
   - `validate_emissions_value()`: Decimal, non-negative, precise
   - `validate_reporting_year()`: Integer, 1900-2100 range
   - `validate_data_quality_score()`: 0-100 range

3. **Normalization Engine** (normalization.py)
   - `normalize_parsed_record()`: Maps CSV columns to standard fields via DataSource.field_mapping
   - `normalize_ingestion()`: Batch normalizes all ParsedRecords in an ingestion
   - Pure functions (testable, no DB side effects)

4. **NormalizedRecord Model** (models.py)
   - Hybrid design: relational fields + JSONB
   - Relational: facility_name, scope_1/2/3_emissions, reporting_year, data_quality_score, is_valid
   - JSONB: normalized_values (full dict), validation_errors (list), data_quality_flags (list)
   - Indexes on facility_name, reporting_year, is_valid for fast queries

5. **REST Endpoint** (views.py)
   - `POST /api/ingest/{ingestion_id}/normalize/`
   - Requires ParsedRecords to exist (idempotent with parse)
   - Returns summary with valid/invalid counts and error details

6. **Serializers** (serializers.py)
   - NormalizationResponseSerializer (response format)
   - NormalizedRecordListSerializer (list view)
   - NormalizedRecordDetailSerializer (detail view with full validation info)

---

## Key Architectural Decisions

### 1. Fixed Schema (vs. Schema-less JSONB)
- ✅ Fixed standard fields enables fast querying and aggregation
- ❌ Schema-less would be more flexible but unqueryable
- **Chosen:** Fixed schema for consistency and performance

### 2. Field Mapping in DataSource
- ✅ Stored in DB, per-source customization, flexible
- ❌ Hard-coded mapping would be simpler but less flexible
- **Chosen:** Field mapping in DataSource model

### 3. Deterministic Normalization
- ✅ Same ParsedRecords = same NormalizedRecords every time
- ✅ Allows safe re-normalization if logic changes
- **Chosen:** Pure functions, no random behavior

### 4. Separate NormalizedRecord Layer
- ✅ Keeps raw → parsed → normalized → approved pipeline clean
- ✅ Easy to debug and audit each stage
- **Chosen:** Separate model between ParsedRecord and EmissionsDataPoint

---

## Data Flow

```
CSV File (uploaded)
    ↓
RawIngestion (raw_csv_content = original text)
    ↓ [Chunk 1.3: Parse with dialect detection]
ParsedRecord (raw_values dict, no validation)
    ↓ [Chunk 1.4: Normalize & Validate]
NormalizedRecord (validated, quality_score, is_valid flag)
    ↓ [Chunk 1.5: Analyst review & approval (TBD)]
EmissionsDataPoint (approved for analytics)
```

---

## API Endpoint

### POST /api/ingest/{ingestion_id}/normalize/

**Request:** No body, ingestion_id in URL

**Response (200 OK):**
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

**Error Responses:**
- `404 Not Found`: RawIngestion doesn't exist
- `400 Bad Request`: No ParsedRecords found (call /parse/ first)
- `500 Internal Server Error`: Unexpected error during normalization

---

## File Changes

### New Files
- `breathe/apps/ingest/validators.py` - Field validators
- `breathe/apps/ingest/normalization.py` - Normalization logic

### Updated Files
- `breathe/apps/ingest/models.py` - Added NormalizedRecord model
- `breathe/apps/ingest/serializers.py` - Added normalization serializers
- `breathe/apps/ingest/views.py` - Added normalize endpoint
- `breathe/apps/ingest/admin.py` - Added NormalizedRecordAdmin

---

## Validation Rules

| Field | Type | Required | Rules | Example |
|-------|------|----------|-------|---------|
| facility_name | string | Yes | Max 255 chars, non-empty | "Plant A" |
| scope_1_emissions | Decimal | No | Non-negative, 15 digits max | 1234.56 |
| scope_2_emissions | Decimal | No | Non-negative, 15 digits max | 567.89 |
| scope_3_emissions | Decimal | No | Non-negative, 15 digits max | 2000.00 |
| reporting_year | int | Yes | 1900-2100 range | 2023 |
| data_quality_score | int | No | 0-100, auto-calculated | 85 |

---

## Data Quality Score Formula

```
Start: 100
Deduction Rules:
  -10 points per validation error (e.g., missing facility_name)
  -5 points per missing optional field (scope_2, scope_3)

Min: 0

Examples:
  - All fields valid: 100
  - Missing scope_2 only: 95
  - Missing scope_2 + scope_3: 90
  - facility_name missing + invalid emissions: 70
```

---

## Testing Coverage

10 integration tests provided in CHUNK_1_4_INTEGRATION_GUIDE.md:
1. ✅ Basic normalization (all valid fields)
2. ✅ Missing optional fields
3. ✅ Validation errors
4. ✅ Different DataSource (Utility vs. SAP)
5. ✅ Idempotent re-normalization
6. ✅ Edge cases (spaces around numbers)
7. ✅ 404 error handling
8. ✅ Dependency validation (parse before normalize)
9. ✅ Data quality score calculation
10. ✅ Mixed valid/invalid in single batch

---

## Next Steps (Chunk 1.5)

**Chunk 1.5: Analyst Review & Approval**
- Create ReviewTask model for analyst workflow
- Implement approval/rejection endpoints
- Create EmissionsDataPoint from approved NormalizedRecords
- Build dashboard for analyst (UI in frontend)

---

## Key Principles

1. **Fixed Schema Drives Consistency**
   - Standard fields for all tenants
   - Fast queries and aggregations
   - Clear validation rules

2. **Pure Functions Enable Testing**
   - Validators, normalization are pure (no DB access)
   - Can unit test millions of validations
   - Easy to debug and refactor

3. **Deterministic = Auditable**
   - Same input = same output
   - Safe to re-normalize
   - Clear error trail

4. **Hybrid Design = Flexibility + Performance**
   - Relational fields: fast, queryable, indexed
   - JSONB fields: flexible, complete audit trail
   - Best of both worlds

5. **Separation of Concerns**
   - Parse: structure (CSV → dict)
   - Normalize: validate (dict → validated dict)
   - Approve: authorize (analyst signs off)

---

## Success Criteria

✅ All 10 integration tests passing
✅ NormalizedRecords created with correct validation_errors
✅ data_quality_score calculated correctly
✅ is_valid flag set based on validation errors
✅ Idempotent re-normalization works
✅ Different DataSources work with different field mappings
✅ Admin panel shows normalized records
✅ Proper error handling (404, 400)
✅ Comprehensive logging
✅ No data loss (ParsedRecords untouched)
