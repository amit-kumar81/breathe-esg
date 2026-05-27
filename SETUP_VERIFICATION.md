# Chunk 1.1 Setup Verification Checklist

Use this to verify that **Chunk 1.1** is complete and working correctly.

---

## Prerequisites Check

- [ ] Docker installed: `docker --version`
- [ ] Docker Compose installed: `docker-compose --version`
- [ ] Python 3.12 (not needed locally, but good to know you have it)
- [ ] All files created (see directory listing below)

---

## File Structure Verification

Verify these files exist in `D:\BreatheESG Assignment\`:

```
✓ docker-compose.yml
✓ Dockerfile.backend
✓ requirements.txt
✓ manage.py
✓ .env.local
✓ .env.example
✓ .gitignore
✓ README.md
✓ SETUP_VERIFICATION.md
✓ breathe/
  ✓ __init__.py
  ✓ settings.py
  ✓ urls.py
  ✓ wsgi.py
✓ apps/
  ✓ tenants/
    ✓ __init__.py
    ✓ models.py
    ✓ admin.py
    ✓ urls.py
  ✓ ingest/
    ✓ __init__.py
    ✓ models.py
    ✓ admin.py
    ✓ urls.py
  ✓ emissions/
    ✓ __init__.py
    ✓ models.py
    ✓ admin.py
    ✓ urls.py
  ✓ review/
    ✓ __init__.py
    ✓ models.py
    ✓ admin.py
    ✓ urls.py
  ✓ audit/
    ✓ __init__.py
    ✓ models.py
    ✓ admin.py
    ✓ urls.py
```

---

## Step 1: Start Docker Containers

Run from `D:\BreatheESG Assignment\`:

```bash
docker-compose up --build
```

**Expected output:**
```
breathe_postgres  | database system is ready to accept connections
breathe_backend   | Migrations applied...
breathe_backend   | Starting development server at 0.0.0.0:8000
```

**Wait 30-60 seconds** for everything to start. The first run is slower.

- [ ] PostgreSQL container starts without errors
- [ ] Backend migrations apply successfully
- [ ] Django dev server runs on port 8000

---

## Step 2: Verify Database Connection

Once containers are running, open a new terminal and run:

```bash
docker-compose exec postgres psql -U breathe_user -d breathe_dev -c "\dt"
```

**Expected output:**
```
 public | audit_audit_log              | table | breathe_user
 public | auth_group                   | table | breathe_user
 public | auth_group_permissions       | table | breathe_user
 public | auth_permission              | table | breathe_user
 public | auth_user                    | table | breathe_user
 public | auth_user_groups             | table | breathe_user
 public | auth_user_user_permissions   | table | breathe_user
 public | django_admin_log             | table | breathe_user
 public | django_content_type          | table | breathe_user
 public | django_migrations            | table | breathe_user
 public | django_session               | table | breathe_user
 public | emissions_emissions_data_point | table | breathe_user
 public | ingest_data_source           | table | breathe_user
 public | ingest_parsed_record         | table | breathe_user
 public | ingest_raw_ingestion         | table | breathe_user
 public | review_review_task           | table | breathe_user
 public | tenants_tenant               | table | breathe_user
```

- [ ] All 16 tables are present
- [ ] Tables have correct names (match model names)

---

## Step 3: Create Django Superuser

```bash
docker-compose exec backend python manage.py createsuperuser
```

**Follow prompts:**
```
Username: admin
Email: admin@example.com
Password: admin123
Password (again): admin123
```

- [ ] Superuser created without errors

---

## Step 4: Verify Django Admin Access

1. Open browser: http://localhost:8000/admin/
2. Log in with superuser credentials (admin / admin123)
3. Verify you see:
   - Tenants
   - Data Sources
   - Raw Ingestions
   - Parsed Records
   - Emissions Data Points
   - Review Tasks
   - Audit Logs
   - Groups
   - Users

- [ ] Can log in to Django admin
- [ ] All 7 custom models are visible in admin
- [ ] No errors in admin interface

---

## Step 5: Create Test Data Via Shell

```bash
docker-compose exec backend python manage.py shell
```

**In the Python shell, run:**

```python
from breathe.apps.tenants.models import Tenant
from breathe.apps.ingest.models import DataSource, RawIngestion, ParsedRecord
from breathe.apps.emissions.models import EmissionsDataPoint
from breathe.apps.review.models import ReviewTask
from breathe.apps.audit.models import AuditLog
from decimal import Decimal
import uuid

# Create tenant
tenant = Tenant.objects.create(
    name="Acme Corporation",
    slug="acme-corp",
    description="Test ESG company"
)
print(f"✓ Created Tenant: {tenant}")

# Create data source (SAP)
ds = DataSource.objects.create(
    tenant_id=tenant,
    source_type="SAP",
    name="SAP Q3 2023 Export",
    description="Quarterly emissions from SAP",
    field_mapping={
        "Plant_Name": "facility_name",
        "Scope1_mtCO2e": "scope_1_emissions",
        "Scope2_mtCO2e": "scope_2_emissions",
        "Year": "year",
        "Methodology": "methodology"
    }
)
print(f"✓ Created DataSource: {ds}")

# Create raw ingestion
ri = RawIngestion.objects.create(
    tenant_id=tenant,
    data_source_id=ds,
    filename="sap_q3_2023.csv",
    file_hash="abc123def456",
    line_count=2,
    raw_content=[
        {"Plant_Name": "Plant A", "Scope1_mtCO2e": "1234.56", "Scope2_mtCO2e": "567.89", "Year": "2023", "Methodology": "IPCC"},
        {"Plant_Name": "Plant B", "Scope1_mtCO2e": "2000.00", "Scope2_mtCO2e": "800.00", "Year": "2023", "Methodology": "GHG Protocol"}
    ]
)
print(f"✓ Created RawIngestion: {ri}")

# Create parsed records
pr1 = ParsedRecord.objects.create(
    ingestion_id=ri,
    tenant_id=tenant,
    source_row_number=1,
    raw_values={"Plant_Name": "Plant A", "Scope1_mtCO2e": "1234.56", "Scope2_mtCO2e": "567.89", "Year": "2023", "Methodology": "IPCC"},
    parsing_errors=[]
)
pr2 = ParsedRecord.objects.create(
    ingestion_id=ri,
    tenant_id=tenant,
    source_row_number=2,
    raw_values={"Plant_Name": "Plant B", "Scope1_mtCO2e": "2000.00", "Scope2_mtCO2e": "800.00", "Year": "2023", "Methodology": "GHG Protocol"},
    parsing_errors=[]
)
print(f"✓ Created ParsedRecords: {pr1}, {pr2}")

# Create emissions data points
edp1 = EmissionsDataPoint.objects.create(
    tenant_id=tenant,
    parsed_record_id=pr1,
    data_source_id=ds,
    facility_name="Plant A",
    scope="SCOPE_1",
    emissions_value=Decimal("1234.56"),
    emissions_unit="mtCO2e",
    year=2023,
    methodology="IPCC",
    is_valid=True,
    normalized_values={
        "facility_name": "Plant A",
        "scope_1_emissions": 1234.56,
        "scope_2_emissions": 567.89,
        "year": 2023,
        "methodology": "IPCC"
    },
    validation_errors=[],
    data_quality_flags=[]
)
edp2 = EmissionsDataPoint.objects.create(
    tenant_id=tenant,
    parsed_record_id=pr2,
    data_source_id=ds,
    facility_name="Plant B",
    scope="SCOPE_1",
    emissions_value=Decimal("2000.00"),
    emissions_unit="mtCO2e",
    year=2023,
    methodology="GHG Protocol",
    is_valid=True,
    normalized_values={
        "facility_name": "Plant B",
        "scope_1_emissions": 2000.00,
        "scope_2_emissions": 800.00,
        "year": 2023,
        "methodology": "GHG Protocol"
    },
    validation_errors=[],
    data_quality_flags=[]
)
print(f"✓ Created EmissionsDataPoints: {edp1}, {edp2}")

# Create review tasks
rt1 = ReviewTask.objects.create(
    tenant_id=tenant,
    emissions_data_point_id=edp1,
    status="PENDING"
)
rt2 = ReviewTask.objects.create(
    tenant_id=tenant,
    emissions_data_point_id=edp2,
    status="PENDING"
)
print(f"✓ Created ReviewTasks: {rt1}, {rt2}")

# Verify counts
print(f"\n✓ Summary:")
print(f"  Tenants: {Tenant.objects.count()}")
print(f"  DataSources: {DataSource.objects.count()}")
print(f"  RawIngestions: {RawIngestion.objects.count()}")
print(f"  ParsedRecords: {ParsedRecord.objects.count()}")
print(f"  EmissionsDataPoints: {EmissionsDataPoint.objects.count()}")
print(f"  ReviewTasks: {ReviewTask.objects.count()}")

# Exit
exit()
```

**Expected output:**
```
✓ Created Tenant: Acme Corporation (acme-corp)
✓ Created DataSource: SAP Q3 2023 Export (SAP)
✓ Created RawIngestion: Ingestion sap_q3_2023.csv (2 rows)
✓ Created ParsedRecords: Row 1 from ..., Row 2 from ...
✓ Created EmissionsDataPoints: Plant A (SCOPE_1) 2023: 1234.5600 mtCO2e, Plant B (SCOPE_1) 2023: 2000.0000 mtCO2e
✓ Created ReviewTasks: Review of ... (PENDING), Review of ... (PENDING)

✓ Summary:
  Tenants: 1
  DataSources: 1
  RawIngestions: 1
  ParsedRecords: 2
  EmissionsDataPoints: 2
  ReviewTasks: 2
```

- [ ] All objects created without errors
- [ ] Object counts are correct (1 tenant, 1 source, 1 ingestion, 2 parsed records, 2 data points, 2 review tasks)

---

## Step 6: Verify Django Admin Shows Test Data

1. Refresh http://localhost:8000/admin/
2. Click into each model:
   - **Tenants**: Should show "Acme Corporation"
   - **Data Sources**: Should show "SAP Q3 2023 Export"
   - **Raw Ingestions**: Should show "sap_q3_2023.csv" with 2 lines
   - **Parsed Records**: Should show 2 rows
   - **Emissions Data Points**: Should show 2 records (Plant A, Plant B)
   - **Review Tasks**: Should show 2 tasks with status "Pending Review"

- [ ] All test data visible in admin
- [ ] Data is correctly associated (Plant A under correct source, etc.)
- [ ] No admin errors or missing fields

---

## Step 7: Verify Foreign Key Relationships

Still in admin, click on one EmissionsDataPoint:

- [ ] Can navigate to its ParsedRecord
- [ ] Can navigate to its DataSource
- [ ] Can navigate to its Tenant
- [ ] All fields are populated correctly

---

## Step 8: Verify Tenant Isolation (In Shell)

```bash
docker-compose exec backend python manage.py shell
```

```python
from breathe.apps.tenants.models import Tenant
from breathe.apps.emissions.models import EmissionsDataPoint

# Create second tenant
tenant2 = Tenant.objects.create(name="Beta Inc", slug="beta-inc")

# Query data points for tenant1
tenant1 = Tenant.objects.get(slug="acme-corp")
acme_data = EmissionsDataPoint.objects.filter(tenant_id=tenant1)
print(f"Acme data points: {acme_data.count()}")  # Should be 2

# Query data points for tenant2
beta_data = EmissionsDataPoint.objects.filter(tenant_id=tenant2)
print(f"Beta data points: {beta_data.count()}")  # Should be 0

# Verify tenant2 has no data even if we try to access all
all_data = EmissionsDataPoint.objects.all()
print(f"Total data points in DB: {all_data.count()}")  # Should be 2 (only acme's)

# Verify using tenant_id correctly filters
acme_only = EmissionsDataPoint.objects.filter(tenant_id__slug="acme-corp")
print(f"ACME data via slug: {acme_only.count()}")  # Should be 2

exit()
```

**Expected output:**
```
Acme data points: 2
Beta data points: 0
Total data points in DB: 2
ACME data via slug: 2
```

- [ ] Tenant isolation works (each tenant sees only their data)

---

## Step 9: Verify Indexes

```bash
docker-compose exec postgres psql -U breathe_user -d breathe_dev -c "\di public.*"
```

**Expected output includes indexes on:**
- tenant_id (all tables)
- data_source_id (RawIngestion, ParsedRecord)
- facility_name, year (EmissionsDataPoint)
- is_valid (EmissionsDataPoint)
- source_row_number (ParsedRecord)
- timestamp (AuditLog)

- [ ] At least 10+ indexes exist

---

## Step 10: Test Migrations Reversibility

```bash
docker-compose exec backend python manage.py migrate ingest zero
```

**Expected output:**
```
Reverting ingest.0001_initial
```

Then reapply:

```bash
docker-compose exec backend python manage.py migrate ingest
```

**Expected output:**
```
Applying ingest.0001_initial
```

- [ ] Migrations can be reversed without errors
- [ ] Migrations can be reapplied without errors

---

## Definition of Done — ALL CHECKS PASSED

- [ ] All files created
- [ ] Docker Compose starts successfully
- [ ] PostgreSQL connected and 16 tables exist
- [ ] Django admin accessible
- [ ] Superuser created
- [ ] Test data created successfully
- [ ] Test data visible in Django admin
- [ ] Foreign key relationships work
- [ ] Tenant isolation verified
- [ ] Indexes created
- [ ] Migrations are reversible

---

## If Something Fails

1. **Check container logs:**
   ```bash
   docker-compose logs backend
   docker-compose logs postgres
   ```

2. **Restart from scratch:**
   ```bash
   docker-compose down -v
   docker-compose up --build
   ```

3. **Check migrations:**
   ```bash
   docker-compose exec backend python manage.py showmigrations
   ```

4. **Check database:**
   ```bash
   docker-compose exec postgres psql -U breathe_user -d breathe_dev -c "SELECT * FROM django_migrations;"
   ```

---

## Chunk 1.1 Complete ✓

If all checks pass, **Chunk 1.1 is complete**. You have:

- ✓ Django project with 5 apps
- ✓ 7 core models with UUID PKs and tenant isolation
- ✓ Hybrid relational + JSONB design
- ✓ Docker Compose local dev setup
- ✓ Initial migrations and test data
- ✓ Django Admin configured (minimal, no over-engineering)

**Next:** Chunk 1.2 (Raw Data Ingestion Endpoint)
