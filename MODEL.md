# Data Model

## Overview

The model is built around one central question: **where did this number come from, and can we prove it?**

ESG data gets audited. Auditors ask which source file produced a specific emissions figure, whether it was edited after upload, who approved it and when. The model answers all of those questions without any reconstruction.

The pipeline is:

```
RawIngestion (raw file, never touched)
  → ParsedRecord (one row dict per CSV row)
    → NormalizedRecord (validated, emission factors applied)
      → EmissionsDataPoint (one per scope per row, ready for review)
        → ReviewTask (analyst sign-off queue)
          → ReviewApproval (immutable decision record)

AuditLog (append-only, covers all model changes)
```

---

## Multi-tenancy

Every table has a `tenant_id` FK. All API querysets are filtered `filter(tenant_id=request.user.profile.tenant)` before anything else happens. One company's data is never accessible by another company's users, not because of encryption but because no query for Tenant A can ever return a row belonging to Tenant B.

I chose FK-per-row (sometimes called "table-per-tenant lite") over row-level security policies or separate schemas because:
- It keeps the Django ORM readable and testable
- It's what most Django multi-tenant apps do at prototype scale
- Separate schemas would require dynamic schema switching, which adds real complexity for what is still a prototype

Tradeoff acknowledged: if the DB is directly queried without going through the API (e.g. a misconfigured admin script), tenant isolation breaks. Proper row-level security would fix that but is out of scope here.

---

## Scope 1 / 2 / 3 Categorization

The three scopes come from the GHG Protocol:

- **Scope 1**: Direct emissions from sources the company owns or controls (boilers, vehicles, on-site combustion). In this app: SAP records for fuel consumption.
- **Scope 2**: Indirect emissions from purchased electricity/steam. In this app: utility meter data converted to CO2e using a grid emission factor.
- **Scope 3**: All other indirect emissions in the value chain. In this app: business travel (flights, hotels, car rentals).

Scope is stored in two places:
1. `EmissionsDataPoint.scope` — an enum (`SCOPE_1`, `SCOPE_2`, `SCOPE_3`) on the final record. This is the field analysts filter and approve by.
2. `NormalizedRecord.scope_1_emissions / scope_2_emissions / scope_3_emissions` — three separate nullable Decimal columns. A single row from SAP might populate all three if the report includes cross-scope data.

Why split into three columns on NormalizedRecord but one scope per EmissionsDataPoint? Because the normalization output is per-row (one facility per CSV row might have all three scopes), but the analytics layer needs one record per scope per facility per year to make aggregation clean. The normalization step fans one NormalizedRecord out into up to three EmissionsDataPoints.

---

## Source-of-Truth Tracking

`RawIngestion.raw_csv_content` stores the original file text verbatim. It is never modified after creation. This is the ground truth.

`RawIngestion.file_hash` (SHA-256) detects duplicate uploads. If you upload the same file twice, you get the same ingestion ID back — no duplicate processing.

The lineage chain is:

```
EmissionsDataPoint.parsed_record_id → ParsedRecord.id
ParsedRecord.ingestion_id → RawIngestion.id
```

So from any final emissions figure you can trace back to the exact row number in the original CSV. `ParsedRecord.raw_values` stores the original row as a JSON dict — exactly what the CSV contained before any transformation.

`ParsedRecord.source_row_number` is the 1-indexed row number in the original file (row 2 = first data row after header). This means you can open the original CSV, jump to that row, and verify the raw value.

---

## Unit Normalization

All final emissions values are stored in **mtCO2e (metric tons CO2 equivalent)**. This is the unit GHG Protocol reporting uses.

**SAP data**: The SAP export uses `tCO2e` in column headers. In scientific notation, 1 tonne CO2e = 1 metric tonne CO2e — they are the same unit. The German scientific convention writes "t" where English writes "mt". No conversion factor needed; the column name difference is handled by the field mapping.

**Utility data**: Portal CSV exports kWh (kilowatt-hours). Conversion: `kWh × 0.000716 = mtCO2e`. The factor 0.000716 is the CEA (Central Electricity Authority, Government of India) CO2 baseline emission factor for 2022-23, expressed as mtCO2e per kWh (equivalent to 0.716 kgCO2e/kWh). This factor is stored in `EmissionsDataPoint.methodology` and in `NormalizedRecord.normalized_values['emission_factor_source']` so auditors can see exactly which factor was applied.

**Travel data**: Each expense type uses a different factor:
- FLIGHT (< 1500 km): 0.255 kgCO2e/passenger-km (ICAO 2023, economy, includes radiative forcing ×1.9)
- FLIGHT (≥ 1500 km): 0.195 kgCO2e/passenger-km (ICAO 2023, long-haul economy)
- HOTEL: 31.3 kgCO2e/night (DEFRA 2023 average hotel)
- CAR/TAXI: 0.171 kgCO2e/km (DEFRA 2023 average car)

All factors are converted to mtCO2e before storage (divide kgCO2e factors by 1,000,000 for per-km values; divide by 1,000 for per-night values stored in that unit).

---

## Audit Trail

`AuditLog` is append-only. The `save()` and `delete()` methods raise `ValueError` — you cannot update or delete an audit record. This is enforced in the model, not just by convention.

Every CREATE, UPDATE, and DELETE on `EmissionsDataPoint`, `NormalizedRecord`, and `ReviewTask` is automatically logged via Django signals (`audit/signals.py`). The log entry includes:
- `object_type` + `object_id`: which record changed
- `action`: CREATE / UPDATE / DELETE
- `change_summary`: `{old_values: {...}, new_values: {...}}` — both before and after state for updates
- `user_id`: who made the change (null for system-generated actions like normalization)
- `ip_address`: for forensic traceability
- `timestamp`: auto-set, never editable

`ReviewApproval` is also immutable after creation. Each analyst decision (approve/reject) creates a new ReviewApproval row. If an analyst approves, then someone overrides with a rejection, there are two ReviewApproval rows — the full decision history is preserved.

---

## Model Reference

| Model | App | Purpose |
|---|---|---|
| `Tenant` | tenants | One company using the platform |
| `UserProfile` | auth | Extends Django User with tenant + role (ADMIN / ANALYST / DATA_PROVIDER / VIEWER) |
| `DataSource` | ingest | Source metadata + field_mapping (CSV column → standard field) |
| `RawIngestion` | ingest | Raw file blob, SHA-256 hash, never modified |
| `ParsedRecord` | ingest | One row from RawIngestion as a JSON dict, unvalidated |
| `NormalizedRecord` | ingest | Validated + emission-factor-applied version of ParsedRecord |
| `EmissionsDataPoint` | emissions | One scope per row, ready for analyst review |
| `ReviewTask` | review | Analyst sign-off queue (PENDING → APPROVED / REJECTED) |
| `ReviewApproval` | review | Immutable record of each analyst decision |
| `AuditLog` | audit | Append-only change log, covers all model mutations |

---

## What This Model Does Not Handle

- **Real-time streaming data**: All ingestion is file-upload-triggered, not event-driven.
- **Multi-period billing proration**: Utility bills that span year boundaries are attributed to the billing start year, not split proportionally. This is consistent with GHG Protocol guidance but loses some precision.
- **Airport coordinate lookup**: Travel distance for flights is taken directly from the Concur export's `Distance_km` column. We do not derive distances from IATA codes in this prototype (that would require an airport database lookup).
- **Emission factor versioning**: The factors are hardcoded in `normalization.py`. A production system would store them in a table with effective dates so historical recalculations use the factor valid at the time.
