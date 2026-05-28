# Breathe ESG — Emissions Data Ingestion Platform

A full-stack ESG emissions data platform: CSV upload → parse → normalize → analyst review → dashboard.

**Live demo:** https://breathe-frontend-t87v.onrender.com

**Stack:** Django 5.2 + DRF · PostgreSQL · React 18 · Docker Compose

---

## Demo Credentials

| Role | Username | Password | Can do |
|---|---|---|---|
| Admin | `admin@demo.com` | `admin123` | Everything |
| Analyst | `analyst@demo.com` | `changeme123` | Review + approve/reject + dashboard |

---

## Sample Files

Three data source types are supported. Sample files are in the repo root:

| Folder | Files | Data source to select |
|---|---|---|
| `sap_samples/` | `sap_ghg_FY2022_annual.csv`, `sap_ghg_FY2023_Q1Q2.csv`, `sap_ghg_FY2023_Q3Q4.csv` | SAP GHG Export |
| `utility_samples/` | `util_bangalore_it_2023.csv`, `util_delhi_offices_2023.csv`, `util_mumbai_facilities_2023.csv` | Utility Portal CSV |
| `travel_samples/` | `travel_Q3_2023_concur_export.csv`, `travel_Q4_2023_concur_export.csv` | Concur Travel Expense Export |

---

## How to Use

1. Log in as `admin@demo.com`
2. Go to **Upload** → select a sample CSV + matching data source → Upload
3. Click **Review & Parse** → Parse CSV → Normalize & Validate
4. Go to **Review** → select a record → Approve or Reject
5. Go to **Dashboard** to see approved emissions totals by scope and year

---

## Pipeline

```
Upload CSV
  → RawIngestion (file stored verbatim, SHA-256 hash for dedup)
    → ParsedRecord (one row per CSV row, unvalidated JSON)
      → NormalizedRecord (validated, emission factors applied, review_status)
        → Dashboard (aggregates APPROVED records only)

AuditLog: append-only, covers all NormalizedRecord mutations
```

---

## Data Model

| Model | App | Purpose |
|---|---|---|
| `Tenant` | tenants | One company using the platform |
| `UserProfile` | auth | Extends Django User with tenant + role (ADMIN/ANALYST/DATA_PROVIDER/VIEWER) |
| `DataSource` | ingest | Source config + field mapping (CSV column → standard field) |
| `RawIngestion` | ingest | Raw file blob, SHA-256 hash, never modified |
| `ParsedRecord` | ingest | One CSV row as JSON dict, unvalidated |
| `NormalizedRecord` | ingest | Validated + emission-factor-applied; carries `review_status` |
| `AuditLog` | audit | Append-only change log |

See `MODEL.md` for full data model documentation.

---

## Emission Factors

- **SAP**: direct tCO2e values from SAP GHG export (no conversion needed)
- **Utility**: `kWh × 0.000716 mtCO2e/kWh` (CEA India 2022-23 grid factor)
- **Travel flights <1500km**: `0.255 kgCO2e/passenger-km` (ICAO 2023, economy)
- **Travel flights ≥1500km**: `0.195 kgCO2e/passenger-km` (ICAO 2023, long-haul)
- **Hotel**: `31.3 kgCO2e/night` (DEFRA 2023)
- **Car/taxi**: `0.171 kgCO2e/km` (DEFRA 2023)

All stored in **mtCO2e** (metric tons CO2 equivalent).

---

## Role-Based Access

| Feature | ADMIN | ANALYST | DATA_PROVIDER | VIEWER |
|---|---|---|---|---|
| Upload / Parse / Normalize | ✓ | ✗ | ✓ | ✗ |
| Review / Approve / Reject | ✓ | ✓ | ✗ | ✗ |
| Dashboard | ✓ | ✓ | ✓ | ✓ |
| All status tabs in Review | ✓ | Pending only | — | — |

Enforced at both API level (DRF permission classes) and frontend (route guards + nav).

---

## Local Development

### Prerequisites
- Docker & Docker Compose

### Start

```bash
docker-compose up --build
```

Backend: http://localhost:8000  
Frontend: http://localhost:5173

### Seed data

```bash
docker-compose exec backend python manage.py seed
```

Creates `admin@demo.com` / `admin123` and `analyst@demo.com` / `changeme123`.

---

## Design Decisions

See `DECISIONS.md` for architecture rationale, `TRADEOFFS.md` for known limitations, `SOURCES.md` for emission factor references, and `MODEL.md` for the full data model.
