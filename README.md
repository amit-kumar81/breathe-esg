# Breathe ESG — Emissions Data Ingestion Platform

A production-quality backend for ESG emissions data ingestion, normalization, and analyst review.

**Stack:** Django 5.2 + DRF | PostgreSQL | Docker Compose | Python 3.12

---

## Project Structure

```
breathe-esg-platform/
  breathe/                    # Django project config
    settings.py              # All configuration
    urls.py                  # URL routing
    wsgi.py                  # WSGI entrypoint
  apps/
    tenants/                 # Multi-tenancy (Tenant model)
    ingest/                  # Raw data ingestion (DataSource, RawIngestion, ParsedRecord)
    emissions/               # Normalized data (EmissionsDataPoint)
    review/                  # Analyst workflows (ReviewTask)
    audit/                   # Audit trail (AuditLog)
  docker-compose.yml         # Local dev environment
  Dockerfile.backend         # Backend container
  requirements.txt           # Python dependencies
  manage.py                  # Django CLI
  .env.local                 # Local config (DO NOT COMMIT)
  .env.example               # Config template (safe to commit)
```

---

## Data Flow

1. **Ingest**: CSV file uploaded → `RawIngestion` (stored as-is, never modified)
2. **Parse**: Each row extracted → `ParsedRecord` (structured dict, unvalidated)
3. **Normalize**: Raw values mapped to schema → `EmissionsDataPoint` (validated, with quality flags)
4. **Review**: Analyst approves/rejects → `ReviewTask` status updated
5. **Audit**: Every change logged → `AuditLog` (append-only, immutable)

---

## Core Models

| Model | Purpose |
|-------|---------|
| `Tenant` | Company using the platform |
| `DataSource` | Metadata about data source (SAP/Utility/Travel) + field mapping |
| `RawIngestion` | Raw file blob (never modified, for auditability) |
| `ParsedRecord` | Single row from file, parsed into dict (unvalidated) |
| `EmissionsDataPoint` | Normalized, validated emissions record (ready for review) |
| `ReviewTask` | Analyst's decision on a data point (PENDING/APPROVED/REJECTED/NEEDS_CLARIFICATION) |
| `AuditLog` | Immutable change log (who, what, when, why) |

### Design Highlights

- **UUID Primary Keys**: All models use UUID for safety in multi-tenant, audit-sensitive contexts
- **Hybrid Relational + JSONB**: Frequently-queried fields are relational (facility_name, year, scope); flexible fields use JSONB (validation_errors, data_quality_flags)
- **Tenant Isolation**: Every model has `tenant_id` FK; all queries filtered by tenant
- **Immutable Audit**: AuditLog records never deleted, readonly in admin
- **Data Lineage**: Every normalized record traces back to its parsed record and raw ingestion

---

## Setup

### Prerequisites

- Docker & Docker Compose installed
- No local PostgreSQL needed (Docker handles it)
- No venv setup needed (Docker handles it)

### Local Development

1. **Clone and enter directory:**
   ```bash
   cd D:\BreatheESG Assignment
   ```

2. **Start services:**
   ```bash
   docker-compose up --build
   ```

   This will:
   - Build the backend image
   - Start PostgreSQL container
   - Run migrations automatically
   - Start Django dev server on http://localhost:8000

3. **Verify:**
   - Django admin: http://localhost:8000/admin/ (no creds yet)
   - API root: http://localhost:8000/api/

### Creating a Superuser (for Django admin access)

```bash
docker-compose exec backend python manage.py createsuperuser
```

Follow prompts. Then log in at http://localhost:8000/admin/

### Creating Initial Data

```bash
docker-compose exec backend python manage.py shell
```

Then in the Python shell:

```python
from breathe.apps.tenants.models import Tenant
from breathe.apps.ingest.models import DataSource

# Create a demo tenant
tenant = Tenant.objects.create(name="Acme Corp", slug="acme-corp")

# Create a data source
ds = DataSource.objects.create(
    tenant_id=tenant,
    source_type="SAP",
    name="SAP Q3 2023 Export",
    field_mapping={
        "Plant_Name": "facility_name",
        "Scope1_mtCO2e": "scope_1_emissions",
        "Year": "year",
    }
)

print(f"Created tenant: {tenant}")
print(f"Created data source: {ds}")
```

---

## Database Migrations

Migrations run automatically on container start. To create new migrations:

```bash
docker-compose exec backend python manage.py makemigrations
```

To apply migrations:

```bash
docker-compose exec backend python manage.py migrate
```

---

## Testing the Schema

Once the container is running:

1. **Access Django shell:**
   ```bash
   docker-compose exec backend python manage.py shell
   ```

2. **Create test data:**
   ```python
   from breathe.apps.tenants.models import Tenant
   from breathe.apps.ingest.models import DataSource, RawIngestion, ParsedRecord
   from breathe.apps.emissions.models import EmissionsDataPoint
   from decimal import Decimal

   # Create tenant
   tenant = Tenant.objects.create(name="Test Corp", slug="test-corp")

   # Create data source
   ds = DataSource.objects.create(
       tenant_id=tenant,
       source_type="SAP",
       name="Test Source",
       field_mapping={"Plant_Name": "facility_name"}
   )

   # Create raw ingestion
   ri = RawIngestion.objects.create(
       tenant_id=tenant,
       data_source_id=ds,
       filename="test.csv",
       file_hash="abc123",
       line_count=1,
       raw_content=[{"Plant_Name": "Plant A", "Scope1": "1000"}]
   )

   # Create parsed record
   pr = ParsedRecord.objects.create(
       ingestion_id=ri,
       tenant_id=tenant,
       source_row_number=1,
       raw_values={"Plant_Name": "Plant A", "Scope1": "1000"},
       parsing_errors=[]
   )

   # Create emissions data point
   edp = EmissionsDataPoint.objects.create(
       tenant_id=tenant,
       parsed_record_id=pr,
       data_source_id=ds,
       facility_name="Plant A",
       scope="SCOPE_1",
       emissions_value=Decimal("1000.00"),
       year=2023,
       is_valid=True,
       normalized_values={"facility_name": "Plant A", "scope_1_emissions": 1000},
       validation_errors=[],
       data_quality_flags=[]
   )

   print(f"Created: {tenant}, {ds}, {ri}, {pr}, {edp}")
   print(f"Emissions data point: {edp}")
   ```

3. **View in admin:**
   - Go to http://localhost:8000/admin/
   - Check Tenants, Data Sources, Raw Ingestions, Parsed Records, Emissions Data Points

---

## Definition of Done (Chunk 1.1)

- [x] Django project initialized (settings, URLs, WSGI)
- [x] 5 apps created with models:
  - Tenants: `Tenant`
  - Ingest: `DataSource`, `RawIngestion`, `ParsedRecord`
  - Emissions: `EmissionsDataPoint`
  - Review: `ReviewTask`
  - Audit: `AuditLog`
- [x] All models use UUID primary keys
- [x] All models have `tenant_id` FK for multi-tenancy
- [x] Hybrid relational + JSONB design applied
- [x] Foreign key relationships are correct
- [x] Indexes added on frequently-queried fields
- [x] Django Admin configured (minimal, no over-engineering)
- [x] Docker Compose setup works locally
- [x] Migrations generated and run without errors
- [x] Can create test data and view in admin
- [x] Can access http://localhost:8000/admin/ after creating superuser

---

## Next Steps

- **Chunk 1.2**: Raw data ingestion endpoint (POST /api/ingest/upload/)
- **Chunk 1.3**: CSV parser & ParsedRecord generation
- **Chunk 1.4**: Schema definition & normalization rules
- **Chunk 1.5**: Normalization & validation pipeline
- **Chunk 1.6**: Audit logging (Django signals)

---

## Architecture Notes

### Why Hybrid Relational + JSONB?

- **Relational fields** (facility_name, year, scope, emissions_value): Fast filtering, aggregation, indexing
- **JSONB fields** (normalized_values, validation_errors, data_quality_flags): Flexible schema, evolves without migrations

Example query:
```python
# Fast relational query
EmissionsDataPoint.objects.filter(
    tenant_id=tenant,
    year=2023,
    scope="SCOPE_1",
    is_valid=True
).values('facility_name').annotate(total=Sum('emissions_value'))
```

### Why UUID Primary Keys?

1. **Traceability**: opaque identifiers don't leak business logic
2. **Multi-tenancy**: IDs are unique across all tenants, safer externally
3. **Audit-sensitive**: harder to guess or enumerate IDs in external APIs
4. **Distributed future**: UUIDs work across multiple databases if sharding needed later

### Why Append-Only Audit Logs?

- Immutable history for compliance (SOX, environmental regulations)
- No "who deleted this?" detective work
- Admin can't edit audit logs (readonly in Django admin)

---

## Troubleshooting

### Migrations fail with "relation does not exist"

This usually means migrations didn't run. Try:
```bash
docker-compose down
docker volume rm breathe-esg-platform_postgres_data
docker-compose up --build
```

### Can't connect to PostgreSQL

Check container logs:
```bash
docker-compose logs postgres
```

Ensure `postgres` service is healthy (wait 10 seconds after startup).

### Django admin login fails

Create a superuser:
```bash
docker-compose exec backend python manage.py createsuperuser
```

---

## License

Breathe ESG Platform
