# Chunk 2.5: Data Export & Reporting - Detailed Explanation

## Overview

Chunk 2.5 implements **Data Export & Reporting** endpoints that allow analysts and data providers to download approved emissions data and view summary statistics. Two main endpoints: export (CSV/JSON) and summary (dashboard metrics).

---

## Architecture Decision 1: CSV Export Using Pandas vs. Manual CSV Writing

### The Decision
We use **manual CSV writing** with Python's `csv` module, NOT pandas DataFrames.

```python
# ✅ Manual CSV writing (Chunk 2.5):
import csv
from io import StringIO

output = StringIO()
writer = csv.DictWriter(output, fieldnames=['Facility', 'Scope 1', ...])
writer.writeheader()
for record in records:
    writer.writerow({...})

response = HttpResponse(output.getvalue(), content_type='text/csv')

# ❌ NOT pandas:
import pandas as pd
df = pd.DataFrame(records)
df.to_csv(...)
```

### Why This Decision

**Dependency Minimization**: CSV module is built-in. No pandas import, no extra dependency.

**Memory Efficiency**: For small exports (< 100k records), manual writing is efficient. Pandas loads entire DataFrame into memory, which uses more RAM for large exports.

**Control**: With manual writing, we control exactly which columns, which order, column naming. Easier to format (e.g., "Scope 1 Emissions (tCO2e)" vs. "scope_1_emissions").

**Performance**: For MVP with reasonable file sizes (< 10k records), manual CSV is faster. Pandas becomes beneficial at 100k+ records.

### When to Switch to Pandas
```python
# If exports >100k records become common:
# - Memory usage becomes issue
# - Need aggregation (pivot tables, groupby)
# - Complex transformations needed
# Then switch to pandas
```

### Alternative Considered: Pandas
```python
df = pd.DataFrame(records)
df.to_csv(output, index=False)
```

**Why Not**: Extra dependency, overkill for MVP. Manual CSV is simpler.

---

## Architecture Decision 2: Two Separate Export Formats (CSV and JSON)

### The Decision
The export endpoint supports both CSV and JSON, selected via `?format=` query parameter.

```python
GET /api/emissions/export/?format=csv
  → File download (CSV)

GET /api/emissions/export/?format=json
  → API response with metadata + records
```

### Why This Decision

**User Flexibility**: 
- CSV users: Excel, Data analysts who work with spreadsheets
- JSON users: Developers, integration systems, dashboards

**Use Cases**:
- CSV: "Download data for review in Excel"
- JSON: "Integrate emissions data into our data warehouse"

**Default Format**: JSON (with metadata). CSV requires file download handling.

### Metadata Included in JSON
```json
{
  "metadata": {
    "export_timestamp": "2026-05-25T10:00:00Z",
    "tenant_name": "Acme Corp",
    "record_count": 1000,
    "filters_applied": {"year": 2023, "status": "APPROVED"},
    "generated_by": "alice"
  },
  "records": [...]
}
```

**Why Metadata**: Auditable. Questions like "Who exported this? When? With what filters?" are answerable from metadata.

### Alternative Considered: CSV Only
```python
# Just CSV, no JSON
GET /api/emissions/export/ → CSV download
```

**Why Rejected**: Developers want JSON for integration. CSV is spreadsheet tool only.

---

## Architecture Decision 3: Default Filter (Approved Records Only)

### The Decision
Without `?status=` query parameter, the export defaults to **APPROVED** records only. Users must explicitly include PENDING or REJECTED.

```python
# Default (approved only):
GET /api/emissions/export/

# With explicit filter:
GET /api/emissions/export/?status=PENDING
GET /api/emissions/export/?status=REJECTED
GET /api/emissions/export/?status=APPROVED
```

### Why This Decision

**Safety Default**: APPROVED records are ready for use. PENDING or REJECTED are draft/rejected data that shouldn't be in a default export.

**Compliance**: ESG reports use APPROVED data. Default export gives the "official" dataset.

**User Expectation**: When an analyst asks "export the data", they mean approved data, not drafts.

### Alternative Considered: All Records by Default
```python
# Export everything
GET /api/emissions/export/ → All records (PENDING, APPROVED, REJECTED)
```

**Why Rejected**: Risk of accidentally including rejected data in reports. Default should be safe.

---

## Architecture Decision 4: Summary Endpoint for Dashboard Metrics

### The Decision
Separate `GET /api/emissions/summary/` endpoint returns aggregated statistics (counts by status, year, facility; averages by quality score; totals by scope).

```json
{
  "total_records": 1000,
  "approved_records": 950,
  "pending_records": 40,
  "rejected_records": 10,
  "by_status": {"APPROVED": 950, "PENDING": 40, ...},
  "by_year": {"2023": 500, "2022": 500},
  "by_facility": {"Plant A": 300, "Plant B": 200, ...},
  "by_quality_tier": {"80-100": 750, "70-80": 150, ...},
  "average_quality_score": 85.2,
  "total_scope_1": 500000.0,
  "total_scope_2": 200000.0,
  "total_emissions": 700000.0
}
```

### Why This Decision

**Frontend Dashboard**: Dashboard needs summary metrics, not full records. Summary endpoint returns exactly what dashboard needs.

**Caching Potential**: Summary is static (for a given day). Can be cached for performance. Full record export can't be cached (might be huge).

**Separation of Concerns**: Export handles records. Summary handles analytics.

**Scalability**: For 100k records, summary query is <1s. Full export might take 10s. Separate endpoints let analytics be fast.

### Real Scenario
Dashboard needs to show:
- "950 of 1000 records approved" (use summary)
- "Download all data" (use export)

One endpoint can't do both efficiently.

### Alternative Considered: Summary Within Export
```python
GET /api/emissions/export/
  → Export records + summary in same response
```

**Why Rejected**: Mixes concerns. Dashboard doesn't need 1000 records, just summary. Export doesn't need summary, just records.

---

## Architecture Decision 5: Quality Tier Grouping (0-40, 40-70, 70-80, 80-100)

### The Decision
Summary groups records by quality score tiers: Poor (0-40), Fair (40-70), Good (70-80), Excellent (80-100).

```python
by_quality_tier = {
  '0-40': 50,    # Poor (50 records)
  '40-70': 100,  # Fair (100 records)
  '70-80': 200,  # Good (200 records)
  '80-100': 650  # Excellent (650 records)
}
```

### Why This Decision

**Actionability**: "650 records in excellent tier" is more useful than "average quality is 82.5". Shows distribution, not just average.

**Auto-Approval Threshold Visibility**: Threshold is 80. Dashboard shows how many records hit it (80-100 tier).

**Quality Improvement Metrics**: "Move records from Fair (40-70) to Good (70-80)" is a measurable goal.

### Tier Meanings
- **0-40 (Poor)**: Missing fields, many errors. Needs major rework.
- **40-70 (Fair)**: Some fields, some errors. Fixable.
- **70-80 (Good)**: Most fields, minor issues. Close to approval.
- **80-100 (Excellent)**: All fields, no errors. Auto-approved.

### Alternative Considered: No Tiers
```python
# Just average
average_quality_score: 82.5
```

**Why Rejected**: Hides distribution. Two datasets with avg 82.5 could have very different distributions (one has 1000 records at 80-100, other has 500 at 40-70 and 500 at 100).

---

## Architecture Decision 6: Filter by Year and Status on Export

### The Decision
Export endpoint supports optional filters: `?year=2023&status=APPROVED`.

```python
GET /api/emissions/export/?format=csv&year=2023&status=APPROVED
  → CSV of 2023 approved records only

GET /api/emissions/export/?format=json&year=2022
  → JSON of 2022 approved records (default status)
```

### Why This Decision

**Common Use Cases**:
- "Give me 2023 data for the annual report" (year filter)
- "Show me all pending records for review" (status filter)

**Combining Filters**: Both can be used together.

**Default Behavior**: No filters = all approved records. Explicit filters override.

### Example Flows
```
Analyst: "Export approved emissions for 2023"
  → GET /api/emissions/export/?year=2023&status=APPROVED

Data provider: "Show me all pending submissions"
  → GET /api/emissions/export/?status=PENDING
```

### Alternative Considered: No Filters
```python
# Always export all approved records
GET /api/emissions/export/
```

**Why Rejected**: Users need flexibility. "Export 2023 data" is a common request.

---

## Architecture Decision 7: Analyst Name in Export (Audit Trail)

### The Decision
CSV/JSON includes "Approved By" column showing which analyst approved each record.

```csv
Facility,Scope 1 Emissions,Status,Approved By,Export Date
Plant A,500.5,APPROVED,alice,2026-05-25 10:00:00
Plant B,600.0,APPROVED,bob,2026-05-25 10:00:00
```

### Why This Decision

**Accountability**: ESG reports need traceability. "Who approved this data?"

**Audit Trail**: Regulatory requirement in many ESG frameworks.

**Compliance**: Sarbanes-Oxley, other regulations require documented approval.

### Limitations
- Only shows last analyst (most recent approval)
- If record was approved, rejected, re-approved, only final approval shown
- For full history, use detail endpoint

### Alternative Considered: No Analyst Info
```csv
Facility,Scope 1 Emissions,Status,Export Date
Plant A,500.5,APPROVED,2026-05-25 10:00:00
```

**Why Rejected**: Loses accountability. "Who approved this?" becomes unanswerable.

---

## Architecture Decision 8: No Advanced Reporting (Graphs, Aggregations)

### The Decision
Chunk 2.5 provides basic export and summary stats. NO complex reporting features:
- No pivot tables
- No trend graphs
- No time-series analysis
- No custom aggregations

All handled in frontend or separate reporting system.

```python
# MVP: Basic summary
summary = {
  'total_records': 1000,
  'by_year': {...},
  'total_scope_1': 500000.0
}

# NOT included: Charts, pivots, trends
# Frontend or Tableau handles visualization
```

### Why This Decision

**Simplicity**: Summary stats are simple and fast. Graphs require charting library (D3, Chart.js, etc.).

**Frontend-Friendly**: React/Vue frontend has charting libraries. Backend doesn't need to render graphs.

**Separation of Concerns**: Backend provides data. Frontend visualizes it.

**Iteration**: Easy to add new metrics if frontend wants. Hard to remove heavy reporting after building it.

### When to Add Reporting
If users ask for:
- "Trend of emissions over time"
- "Which facilities are biggest emitters"
- "Year-over-year comparison"

Then build reporting layer (Metabase, Superset, or custom dashboard).

### Alternative Considered: Full Reporting System
```python
# Backend generates charts, reports, PDFs
GET /api/emissions/report/by-facility/
  → Chart data
GET /api/emissions/report/trend/
  → Time-series analysis
```

**Why Deferred**: Premature optimization. Do basic export first. If users ask for fancy reports, build them then.

---

## Architecture Decision 9: Metadata in JSON Export

### The Decision
JSON export includes metadata object with context about the export.

```json
{
  "metadata": {
    "export_timestamp": "2026-05-25T10:00:00Z",
    "export_format": "json",
    "tenant_name": "Acme Corp",
    "record_count": 1000,
    "filters_applied": {"year": 2023, "status": "APPROVED"},
    "generated_by": "alice"
  },
  "records": [...]
}
```

### Why This Decision

**Auditability**: When was this exported? Who did it? With what filters?

**Integration Tracking**: Systems importing data can log metadata for lineage.

**Debugging**: "This data looks stale" → Check export_timestamp.

**Compliance**: Full context for audit reports.

### CSV Doesn't Include Metadata
CSV file can't easily include metadata without polluting the data. So only JSON has metadata object. CSV has export date in a column.

### Alternative Considered: No Metadata
```json
[...]  // Just the records array
```

**Why Rejected**: Loses context. Questions like "when was this exported" become unanswerable.

---

## Architecture Decision 10: Multi-Tenant Isolation in Export

### The Decision
Users can only export their tenant's data. TenantQuerySetMixin auto-filters.

```python
class EmissionsExportViewSet(TenantQuerySetMixin, ...):
    # get_queryset() filters by request.user.profile.tenant_id automatically
```

### Why This Decision

**Security**: User A can't export User B's emissions data.

**Consistency**: Matches isolation in Chunk 2.3 and 2.4.

**Compliance**: Data stays within tenant boundary.

---

## Summary of Decisions

| Decision | Why | Trade-Off |
|----------|-----|-----------|
| **Manual CSV, not pandas** | Simpler, no extra dependency | Slower for huge files (>100k rows) |
| **Two formats (CSV + JSON)** | Flexibility for different users | Extra endpoint to maintain |
| **Default to approved records** | Safety default | Need explicit filter for others |
| **Separate summary endpoint** | Dashboard needs metrics, not records | Two endpoints instead of one |
| **Quality tiers** | Shows distribution, not just average | Added complexity |
| **Year and status filters** | Common use cases | Query parameter validation |
| **Analyst name in export** | Accountability and audit | Only shows latest approval |
| **No advanced reporting** | Simplicity for MVP | Defer graphs/trends to later |
| **Metadata in JSON** | Auditability | Extra response size |
| **Multi-tenant isolation** | Security | All endpoints filtered |

---

## Testing Strategy

This chunk is validated through 10+ integration tests (see INTEGRATION_GUIDE):

1. **Export CSV Default**: GET /api/emissions/export/?format=csv → approved records in CSV
2. **Export JSON Default**: GET /api/emissions/export/?format=json → approved records + metadata
3. **Filter by Year**: GET /api/emissions/export/?year=2023 → only 2023 records
4. **Filter by Status**: GET /api/emissions/export/?status=PENDING → pending records
5. **Combined Filters**: GET /api/emissions/export/?year=2023&status=APPROVED → 2023 approved
6. **CSV Format**: Proper headers, all fields, valid CSV syntax
7. **JSON Format**: Valid JSON with metadata object and records array
8. **Summary Endpoint**: GET /api/emissions/summary/ → all metrics returned
9. **Quality Tiers**: Summary includes by_quality_tier with 4 tiers
10. **Multi-Tenant Isolation**: Users only see own tenant's data in export
11. **Empty Export**: No records → appropriate error message
12. **Analyst Name**: Export includes "Approved By" column

---

This chunk completes the data export and basic reporting layer. Advanced analytics (Tableau, Metabase) can be integrated later if needed.
