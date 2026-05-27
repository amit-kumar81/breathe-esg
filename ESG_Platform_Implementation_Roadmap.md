# ESG Emissions Data Ingestion Platform — Implementation Roadmap

**Master Principle:** Real-world engineering, no toy code. Each chunk should be defensible to a senior engineer. Avoid hallucination by being specific about inputs, outputs, and tradeoffs.

---

## ARCHITECTURE OVERVIEW

### System Design Philosophy

This is an **ingest-normalize-review** system. Data flows:

1. **Ingest**: Raw emissions data arrives from multiple sources (CSV, API, unstructured)
2. **Normalize**: Data is mapped to standardized schemas, validated, and flagged for issues
3. **Review**: Analysts inspect, approve, reject, or request corrections
4. **Audit**: Every change is tracked with who, what, when, and why

### Core Entities (No Overkill)

```
Tenant (Company using the platform)
  └─ DataSource (a file, API, or form submission)
       └─ RawIngestion (raw data as received)
            └─ ParsedRecord (structured record from raw data)
                 └─ EmissionsDataPoint (normalized, schema-validated)
                      └─ Review (analyst feedback and approval state)
                           └─ AuditLog (who did what, when)
```

### Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Backend | Django 4.2 + DRF | Mature, strong ORM, good for auditing |
| Frontend | React 18 + TanStack Query | Minimal friction, real-time data sync |
| Database | PostgreSQL | JSONB for flexible schemas, strong transactions |
| Deployment | Railway/Render | Simple, managed, good for MVP |
| Secrets | Environment variables | Start simple, migrate to Vault later if needed |

### Repo Structure (Keep It Flat)

```
breathe-esg-platform/
  backend/
    manage.py
    requirements.txt
    breathe/
      settings.py
      urls.py
    apps/
      ingest/          # Ingestion logic
      emissions/       # Data models
      review/          # Analyst workflows
      audit/           # Audit trail
    tests/
  frontend/
    package.json
    src/
      pages/           # React pages
      components/      # Reusable components
      hooks/           # Custom hooks (data fetching, forms)
      api/             # API client wrapper
    tests/
  docker-compose.yml   # Local dev only
  README.md
```

---

## PHASE 1: DATA MODELING & INGESTION CORE

**Goal**: Set up the database schema and ingest raw data without losing information.

### Chunk 1.1: Django Project Setup & Database Schema

**Input:** Fresh Django project, PostgreSQL connection string
**Output:** Migrations for core data models, database initialized

**Implementation Points:**

1. Create Django project: `django-admin startproject breathe .`
2. Create apps: `manage.py startapp ingest`, `manage.py startapp emissions`
3. Define models in `emissions/models.py`:

   ```
   - Tenant (multi-tenancy key)
   - DataSource (file/API/form metadata)
   - RawIngestion (blob of raw data + metadata like filename, upload time)
   - ParsedRecord (structured JSON from raw data)
   - EmissionsDataPoint (normalized, validated record)
   - ReviewTask (analyst feedback loop)
   - AuditLog (every change tracked)
   ```

4. Use Django's `JSONField` for flexible schema handling (PostgreSQL-backed)
5. Add indexes on: tenant_id, data_source_id, review_status, created_at
6. Create initial migration, test with `python manage.py migrate`

**Tradeoff:** Start with simple UUID PKs and tenant_id on every model. No fancy sharding yet—one DB, one schema, isolate via tenant_id in queries.

**Definition of Done:**
- [ ] Models created, migrations generated
- [ ] Can insert a Tenant, DataSource, and RawIngestion record
- [ ] Foreign key relationships are correct
- [ ] Migrations are reversible

---

### Chunk 1.2: Raw Data Ingestion Endpoint

**Input:** CSV file from analyst, JSON request body with metadata
**Output:** RawIngestion record created, no data loss, no processing yet

**Implementation Points:**

1. Create `ingest/views.py` with a POST endpoint `/api/ingest/upload`
2. Accept multipart/form-data: file + tenant_id + source_name
3. Store raw file content in `RawIngestion.raw_content` (JSONB or binary, depending on file type)
4. Store metadata: filename, upload_time, file_hash (SHA256 for idempotency), line count
5. Return: `{"ingestion_id": "uuid", "status": "received", "line_count": 42}`
6. **Do not parse or validate yet**—just store as-is

**Tradeoff:** Store raw content in DB for auditability. If files are huge (>100MB), switch to blob storage (S3) later.

**Security:**
- Validate tenant ownership (user can only upload to their tenant)
- Limit file size to 10MB initially
- Reject unknown MIME types (CSV only for now)

**Definition of Done:**
- [ ] Endpoint accepts a CSV file and stores it
- [ ] File hash is computed and stored (for duplicate detection)
- [ ] RawIngestion record includes upload metadata
- [ ] No parsing errors if file is malformed
- [ ] Idempotent: re-uploading same file returns same ingestion_id

---

### Chunk 1.3: CSV Parser & ParsedRecord Generation

**Input:** RawIngestion record with raw CSV content
**Output:** ParsedRecords created from each row, with source row number preserved

**Implementation Points:**

1. Create `ingest/parser.py` with a function `parse_csv_ingestion(ingestion_id)`
2. Read `RawIngestion.raw_content`, parse CSV
3. For each row:
   - Map to a dict: `{"source_row": 2, "raw_values": {"column1": "value1", ...}, "parsing_errors": []}`
   - Create a `ParsedRecord` with this JSON
   - **Do not validate yet**—just structure
4. Track errors: missing columns, type mismatches (but don't fail, just flag)
5. Store `source_row_number` so analysts can trace back to the file

**Tradeoff:** Accept "bad" rows and flag them. Analysts need to see what went wrong, not get a generic parse error.

**Example ParsedRecord:**
```json
{
  "ingestion_id": "...",
  "source_row_number": 5,
  "raw_values": {
    "facility_name": "Plant A",
    "scope_1_emissions_mtco2e": "1234.56",
    "year": "2023"
  },
  "parsing_errors": []
}
```

**Definition of Done:**
- [ ] Parse CSV without crashing on bad rows
- [ ] Each row becomes a ParsedRecord
- [ ] Malformed rows are flagged, not skipped
- [ ] Can trace back from ParsedRecord to source row in file

---

### Chunk 1.4: Schema Definition & Normalization Rules

**Input:** Business requirements for ESG data (what fields matter, what are valid values)
**Output:** A configuration file defining the normalized schema

**Implementation Points:**

1. Create `emissions/schema.py`:
   - Define target fields: `facility_name`, `scope_1_emissions`, `scope_2_emissions`, `scope_3_emissions`, `year`, `methodology`, `data_quality_flag`
   - For each field:
     - Expected data type (string, float, int, date)
     - Validation rules (min/max, regex, allowed values)
     - Is it required?
     - Conversion rules (e.g., "tCO2e" → convert to "mtCO2e")
   
   ```python
   EMISSIONS_SCHEMA = {
       "facility_name": {
           "type": "string",
           "required": True,
           "min_length": 1,
           "max_length": 255
       },
       "scope_1_emissions": {
           "type": "float",
           "required": True,
           "min": 0,
           "unit": "mtCO2e"
       },
       "year": {
           "type": "int",
           "required": True,
           "min": 2000,
           "max": 2100
       }
   }
   ```

2. Create a **field mapping table** (or Django model):
   - Source file column names → normalized field names
   - Example: "Plant_Name" → "facility_name", "Metric_Tons_CO2" → "scope_1_emissions"
   - This is **per-DataSource** (each file upload can have different column names)

**Tradeoff:** Don't try to infer schemas. Analysts provide a mapping. Start with manual mapping, automate later if pattern emerges.

**Definition of Done:**
- [ ] Schema defined for at least 3 core ESG fields
- [ ] Mapping table allows per-source column name translation
- [ ] Can describe validation rules for each field
- [ ] Schema is versioned (in case it changes)

---

### Chunk 1.5: Normalization & Validation Pipeline

**Input:** ParsedRecord with raw values + schema mapping
**Output:** EmissionsDataPoint (validated, normalized) or validation errors

**Implementation Points:**

1. Create `ingest/normalizer.py` with function `normalize_and_validate(parsed_record, data_source)`
2. Steps:
   a. Apply field mapping: "Plant_Name" → "facility_name"
   b. Type conversion: "1234.56" (string) → 1234.56 (float)
   c. Unit conversion: "tCO2e" → "mtCO2e"
   d. Validate against schema rules
   e. Flag data quality issues (e.g., "missing methodology", "out-of-range value")
3. Output:
   ```json
   {
       "normalized_values": {
           "facility_name": "Plant A",
           "scope_1_emissions": 1234.56,
           "year": 2023
       },
       "validation_errors": [],
       "data_quality_flags": [
           {"field": "methodology", "severity": "warning", "message": "Methodology not provided"}
       ],
       "is_valid": true
   }
   ```
4. Create `EmissionsDataPoint` with this data (whether valid or not)
5. Store validation results so analysts can review

**Tradeoff:** Accept some "invalid" records and let analysts decide. Don't silently drop data.

**Definition of Done:**
- [ ] Can normalize a valid CSV row to EmissionsDataPoint
- [ ] Validation errors are captured, not fatal
- [ ] Data quality flags are generated (e.g., missing optional fields)
- [ ] Unit conversions work (tCO2e → mtCO2e)
- [ ] Normalized data is traceable back to source row

---

### Chunk 1.6: Audit Logging (Every Change)

**Input:** Any change to EmissionsDataPoint (creation, update, delete)
**Output:** AuditLog record created automatically

**Implementation Points:**

1. Create `audit/models.py`:
   ```
   AuditLog:
     - object_type (string: "EmissionsDataPoint", "ParsedRecord", etc.)
     - object_id (UUID of the object)
     - tenant_id
     - action (string: "created", "updated", "deleted", "reviewed")
     - change_summary (JSON: {"field": "scope_1_emissions", "old": 100, "new": 200})
     - user_id (analyst who made change)
     - timestamp
     - ip_address
   ```
2. Use Django signals to auto-log on model save/delete
3. For updates: capture old vs. new values
4. Ensure tenant isolation (can't query other tenant's audit logs)

**Tradeoff:** Start simple: auto-log everything. No access control yet (analysts see all), but audit trail exists.

**Definition of Done:**
- [ ] Every EmissionsDataPoint creation is logged
- [ ] Updates show old vs. new values
- [ ] Analysts can query audit trail for a record
- [ ] Audit logs can't be modified or deleted (append-only)

---

## PHASE 2: API & BACKEND INFRASTRUCTURE

**Goal**: Expose data for ingestion, retrieval, and review workflow.

### Chunk 2.1: Django REST Framework Setup & Serializers

**Input:** Django models from Phase 1
**Output:** API endpoints that serialize data cleanly

**Implementation Points:**

1. Install `djangorestframework` and `django-filter`
2. Create serializers in `ingest/serializers.py` and `emissions/serializers.py`:
   ```python
   class EmissionsDataPointSerializer(serializers.ModelSerializer):
       # Flatten normalized_values for easier frontend consumption
       facility_name = serializers.CharField(source="normalized_values.facility_name")
       scope_1_emissions = serializers.FloatField(source="normalized_values.scope_1_emissions")
       # Include audit trail (recent changes)
       recent_changes = serializers.SerializerMethodField()
   ```
3. Implement list/detail views with filtering:
   - `GET /api/emissions/` → list all EmissionsDataPoints for tenant, with filtering by year/status
   - `GET /api/emissions/{id}/` → detail view with full history
   - `GET /api/emissions/{id}/audit/` → audit trail for this record
4. Use `DjangoFilterBackend` for filtering by status, year, data_source

**Tradeoff:** Nest related data (audit logs, validation errors) in the serializer. Keep it flat enough for frontend to consume easily.

**Definition of Done:**
- [ ] Can list EmissionsDataPoints as JSON
- [ ] Detail endpoint includes audit trail
- [ ] Filtering by year, status works
- [ ] Serializer handles missing/invalid fields gracefully
- [ ] API returns 200 for valid, 400 for bad requests

---

### Chunk 2.2: Analyst Review Workflow API

**Input:** EmissionsDataPoint with validation issues
**Output:** API for analyst to approve, reject, or request correction

**Implementation Points:**

1. Create `review/models.py`:
   ```
   ReviewTask:
     - emissions_data_point_id
     - tenant_id
     - status (enum: "pending", "approved", "rejected", "needs_clarification")
     - analyst_feedback (string: why approved or rejected)
     - analyst_id
     - created_at
     - reviewed_at
   ```
2. Create endpoints:
   - `GET /api/review/pending/` → list tasks awaiting analyst review
   - `POST /api/review/{task_id}/approve/` → analyst approves
   - `POST /api/review/{task_id}/reject/` → analyst rejects with reason
   - `POST /api/review/{task_id}/request_clarification/` → ask for more info
3. When approved/rejected, create an AuditLog entry
4. Rejection should not delete the record—just mark its status

**Tradeoff:** Simple state machine. No complex workflows (e.g., escalation to manager). Start with analyst as final authority.

**Definition of Done:**
- [ ] Analyst can see pending reviews
- [ ] Can approve/reject with reason
- [ ] Rejection creates audit trail
- [ ] Rejected records still exist (not deleted)
- [ ] Review status is queryable

---

### Chunk 2.3: Multi-Tenancy Isolation

**Input:** API endpoints from earlier chunks
**Output:** Requests are automatically scoped to the logged-in user's tenant

**Implementation Points:**

1. Create `auth/models.py`:
   ```
   User:
     - username
     - email
     - tenant_id (FK to Tenant)
   ```
2. Create custom JWT or session-based auth:
   - Login endpoint: `POST /api/auth/login/` with username + password
   - Returns token with tenant_id embedded
3. Create middleware/permission class:
   ```python
   class TenantIsolationPermission(permissions.BasePermission):
       def has_object_permission(self, request, view, obj):
           return obj.tenant_id == request.user.tenant_id
   ```
4. Apply to all viewsets: `permission_classes = [TenantIsolationPermission]`
5. Filter querysets by tenant:
   ```python
   def get_queryset(self):
       return EmissionsDataPoint.objects.filter(
           tenant_id=self.request.user.tenant_id
       )
   ```

**Tradeoff:** No row-level encryption yet. Rely on SQL WHERE clause. If you need stronger isolation, add schema-based multi-tenancy later.

**Definition of Done:**
- [ ] User logs in with tenant credentials
- [ ] API calls are scoped to their tenant
- [ ] Can't query another tenant's data even with direct ID
- [ ] Token includes tenant_id
- [ ] Tests verify isolation (user A can't see user B's data)

---

### Chunk 2.4: Ingestion Workflow Endpoints

**Input:** User uploads a CSV
**Output:** Series of API calls that move data through ingest → parse → normalize → review

**Implementation Points:**

1. Create view `IngestionViewSet` with steps:
   - `POST /api/ingest/upload/` → store RawIngestion
   - `POST /api/ingest/{id}/parse/` → generate ParsedRecords
   - `POST /api/ingest/{id}/normalize/` → create EmissionsDataPoints
   - `GET /api/ingest/{id}/status/` → check progress

2. Return progress at each step:
   ```json
   {
       "ingestion_id": "...",
       "status": "normalized",
       "steps_completed": ["upload", "parse", "normalize"],
       "summary": {
           "total_rows": 100,
           "parsed_rows": 100,
           "valid_rows": 95,
           "rows_with_warnings": 3,
           "rows_with_errors": 2
       }
   }
   ```

3. Each step can be called independently (idempotent):
   - Re-uploading same file = idempotent (same ingestion_id)
   - Re-parsing = re-generates ParsedRecords (incremental, no dupes)

**Tradeoff:** No async/Celery yet. Keep it synchronous for simplicity. If file parsing takes >2s, add async later.

**Definition of Done:**
- [ ] Can upload CSV and get ingestion_id
- [ ] Can parse and see row count + errors
- [ ] Can normalize and see validation issues
- [ ] Progress is trackable
- [ ] Each step is idempotent

---

### Chunk 2.5: Data Export & Reporting

**Input:** EmissionsDataPoints (approved ones)
**Output:** CSV or JSON export for analyst

**Implementation Points:**

1. Create endpoint `GET /api/emissions/export/`:
   - Query params: `format` (csv or json), `year` (optional), `status` (optional)
   - Return filtered EmissionsDataPoints
2. For CSV: use `pandas.DataFrame` to structure and export
3. Include metadata: export timestamp, number of records, tenant name
4. Optionally include audit trail (analyst can see who approved each record)

**Tradeoff:** No advanced reporting yet (graphs, aggregations). Just export what's in the DB. Build viz layer in frontend.

**Definition of Done:**
- [ ] Can export approved records as CSV
- [ ] Export includes normalized values
- [ ] Can filter by year/status
- [ ] File is downloadable, properly formatted

---

## PHASE 3: FRONTEND & ANALYST INTERFACE

**Goal**: Give analysts a usable interface to upload, review, and approve data.

### Chunk 3.1: React Project Setup & API Client

**Input:** Backend API (from Phase 2)
**Output:** React project with reusable API client and hooks

**Implementation Points:**

1. Create React app: `npx create-react-app frontend`
2. Install dependencies: `react-router-dom`, `@tanstack/react-query`, `axios`
3. Create `src/api/client.js`:
   ```javascript
   const apiClient = axios.create({
       baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000/api"
   });
   
   // Attach JWT token to requests
   apiClient.interceptors.request.use(config => {
       const token = localStorage.getItem("token");
       if (token) config.headers.Authorization = `Bearer ${token}`;
       return config;
   });
   ```
4. Create custom hooks: `useEmissions()`, `useIngestions()`, `useReviewTasks()`
   ```javascript
   export function useEmissions() {
       return useQuery({
           queryKey: ["emissions"],
           queryFn: () => apiClient.get("/emissions/").then(r => r.data)
       });
   }
   ```
5. Create error boundaries and error handling
6. Add loading states and spinners

**Tradeoff:** Start simple with React Query. No Redux. Add state management if it gets messy.

**Definition of Done:**
- [ ] Can call backend API from React
- [ ] JWT token is persisted and sent on requests
- [ ] Loading/error/success states work
- [ ] API errors are displayed to user

---

### Chunk 3.2: Login & Authentication UI

**Input:** Backend auth endpoints
**Output:** Login form, persistent session

**Implementation Points:**

1. Create `src/pages/LoginPage.jsx`:
   - Email/password form
   - POST to `/api/auth/login/`
   - Store JWT token in localStorage
   - Redirect to dashboard on success
2. Create `src/components/ProtectedRoute.jsx`:
   - Checks for token
   - Redirects to login if missing
3. Add logout: clear token, redirect to login

**Tradeoff:** No multi-factor auth yet. Just username/password.

**Definition of Done:**
- [ ] User can log in with valid credentials
- [ ] Token is stored
- [ ] Protected routes require login
- [ ] Can log out

---

### Chunk 3.3: File Upload & Ingestion UI

**Input:** RawIngestion endpoints from backend
**Output:** Upload form, progress tracking

**Implementation Points:**

1. Create `src/pages/UploadPage.jsx`:
   - File input (accept .csv only)
   - Name/description field
   - Submit button
2. On submit:
   - POST to `/api/ingest/upload/`
   - Show progress: "Uploading..."
   - Return ingestion_id
   - Redirect to review page for this ingestion
3. Create `src/pages/IngestionReviewPage.jsx`:
   - Show ingestion status
   - List of parsed rows (or errors)
   - Parse button (if not yet parsed)
   - Normalize button (if not yet normalized)
4. Show summary: "100 rows parsed, 95 valid, 3 warnings, 2 errors"

**Tradeoff:** No drag-and-drop yet. Simple file input works.

**Definition of Done:**
- [ ] User can upload CSV
- [ ] Progress is shown
- [ ] Can see parsed rows and errors
- [ ] Can trigger normalization
- [ ] Summary is displayed

---

### Chunk 3.4: Analyst Review Dashboard

**Input:** ReviewTasks from backend
**Output:** Table of pending reviews, ability to approve/reject

**Implementation Points:**

1. Create `src/pages/ReviewDashboard.jsx`:
   - Table of pending review tasks
   - Columns: facility_name, scope_1_emissions, year, status, data_quality_flags
   - Sort by: pending first, then by year
2. Clicking a row opens detail modal with:
   - Full EmissionsDataPoint data
   - Validation errors and warnings
   - Audit trail (who uploaded, when)
   - Approve/Reject buttons
3. On approve/reject:
   - POST to `/api/review/{task_id}/approve/`
   - Add optional reason/feedback
   - Show confirmation
   - Update table (remove from pending)

**Tradeoff:** No bulk approve yet. One-by-one is fine for MVP.

**Definition of Done:**
- [ ] Analyst sees list of pending reviews
- [ ] Can click to see details
- [ ] Can approve/reject with reason
- [ ] Approved records disappear from pending list
- [ ] Audit trail is visible

---

### Chunk 3.5: Data Visualization & Explorer

**Input:** Approved EmissionsDataPoints
**Output:** Simple dashboard showing trends

**Implementation Points:**

1. Create `src/pages/DashboardPage.jsx` with:
   - Total emissions by scope (bar chart using Recharts)
   - Emissions by year (line chart)
   - Number of facilities
   - Data completeness (% of required fields filled)
2. Add filters: year, scope, facility
3. Show a table of all approved records below

**Tradeoff:** No fancy ML predictions. Just aggregate and visualize what's there.

**Definition of Done:**
- [ ] Dashboard shows basic KPIs
- [ ] Charts render correctly
- [ ] Filtering works
- [ ] Data is accurate and traceable

---

## PHASE 4: DEPLOYMENT & OPERATIONS

**Goal**: Get the system running on a cloud platform, with monitoring and easy rollback.

### Chunk 4.1: Dockerization

**Input:** Django + React source code
**Output:** Docker images for backend and frontend

**Implementation Points:**

1. Create `Dockerfile.backend`:
   ```dockerfile
   FROM python:3.11
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   CMD ["gunicorn", "breathe.wsgi:application", "--bind", "0.0.0.0:8000"]
   ```
2. Create `Dockerfile.frontend`:
   ```dockerfile
   FROM node:18 AS build
   WORKDIR /app
   COPY package*.json .
   RUN npm ci
   COPY . .
   RUN npm run build
   
   FROM node:18
   RUN npm install -g serve
   COPY --from=build /app/build /app/build
   CMD ["serve", "-s", "build", "-l", "3000"]
   ```
3. Create `docker-compose.yml` for local dev:
   - Backend on port 8000
   - Frontend on port 3000
   - PostgreSQL on port 5432
4. Test locally: `docker-compose up`

**Tradeoff:** No Kubernetes yet. Docker Compose for dev, single containers on Render/Railway for prod.

**Definition of Done:**
- [ ] Backend and frontend build successfully
- [ ] Can run `docker-compose up` and access both services
- [ ] Database migrations run automatically
- [ ] No hardcoded secrets in Dockerfile

---

### Chunk 4.2: Environment Configuration & Secrets

**Input:** Dockerized app
**Output:** Config system that works locally and in production

**Implementation Points:**

1. Create `.env.local` (for local dev, not committed):
   ```
   DEBUG=True
   DATABASE_URL=postgresql://user:pass@localhost:5432/breathe_dev
   SECRET_KEY=local-dev-key-change-in-prod
   ALLOWED_HOSTS=localhost,127.0.0.1
   ```
2. Update Django settings to read from env:
   ```python
   import os
   from urllib.parse import urlparse
   
   DATABASE_URL = os.getenv("DATABASE_URL")
   SECRET_KEY = os.getenv("SECRET_KEY")
   DEBUG = os.getenv("DEBUG", "False") == "True"
   ```
3. For production (Render/Railway):
   - Don't commit `.env.local`
   - Set environment variables in platform dashboard
   - Use strong SECRET_KEY
   - DATABASE_URL comes from managed DB

4. Create `.env.example` (safe to commit):
   ```
   DEBUG=False
   DATABASE_URL=postgresql://user:password@host:5432/db
   SECRET_KEY=change-me-in-production
   ```

**Tradeoff:** No vault/HashiCorp. Env vars are sufficient for MVP.

**Definition of Done:**
- [ ] Can run locally with `.env.local`
- [ ] No secrets in code
- [ ] Can set env vars on Render/Railway
- [ ] `.env.local` is in `.gitignore`

---

### Chunk 4.3: Database Migrations & Initial Data

**Input:** Django models
**Output:** Automated migrations + seed data for demo

**Implementation Points:**

1. Track migrations in Git:
   - `python manage.py makemigrations` creates migration files
   - Commit migration files to Git
   - On deploy: `python manage.py migrate` runs them

2. Create seed data (demo tenant + user):
   ```python
   # fixtures/initial_data.json or management/command/seed.py
   from django.core.management.base import BaseCommand
   from breathe.apps.tenants.models import Tenant
   from breathe.apps.auth.models import User
   
   class Command(BaseCommand):
       def handle(self, *args, **options):
           tenant, _ = Tenant.objects.get_or_create(
               name="Demo Company",
               defaults={"slug": "demo-company"}
           )
           User.objects.get_or_create(
               username="analyst@demo.com",
               defaults={
                   "email": "analyst@demo.com",
                   "tenant_id": tenant.id,
                   "password": "changeme123"  # Hash this!
               }
           )
   ```
3. Run on first deploy only: document in README

**Tradeoff:** Manual seeding for MVP. Automate with migrations later if needed.

**Definition of Done:**
- [ ] Migrations are tracked in Git
- [ ] Can run migrations on new deployment
- [ ] Demo data (tenant + user) can be created
- [ ] No errors in migration history

---

### Chunk 4.4: Deployment to Render or Railway

**Input:** Dockerized app, environment configuration
**Output:** App running on cloud platform

**Implementation Points (Render):**

1. Connect GitHub repo to Render
2. Create web service:
   - Runtime: Docker
   - Branch: main
   - Dockerfile: `Dockerfile.backend`
   - Environment variables: set DATABASE_URL, SECRET_KEY, etc.
3. Create PostgreSQL database service:
   - Render manages backups, SSL, networking
   - Copy connection string to environment variable
4. Create static file hosting (frontend):
   - Separate web service for React build
   - Or serve frontend from backend (simpler for MVP)
5. Deploy: push to main, Render auto-deploys

**Or Railway:**
1. Connect GitHub repo
2. Add services: PostgreSQL, backend, frontend
3. Set environment variables
4. Deploy

**Tradeoff:** Managed databases are simpler but pricier. Start here, migrate to self-managed if cost is issue.

**Definition of Done:**
- [ ] Backend deploys and is accessible
- [ ] Frontend deploys and is accessible
- [ ] Database is running and connected
- [ ] Can log in and upload a CSV end-to-end
- [ ] HTTPS is enabled
- [ ] Logs are visible in platform dashboard

---

### Chunk 4.5: Monitoring & Error Logging

**Input:** Running app on Render/Railway
**Output:** Error visibility and basic monitoring

**Implementation Points:**

1. Add Sentry (error logging):
   ```bash
   pip install sentry-sdk
   ```
   ```python
   # settings.py
   import sentry_sdk
   sentry_sdk.init(
       dsn=os.getenv("SENTRY_DSN"),
       environment="production"
   )
   ```
2. Add health check endpoint:
   ```python
   @api_view(['GET'])
   def health(request):
       return Response({"status": "ok", "version": "0.1.0"})
   ```
3. Set up logs:
   - Render/Railway dashboard shows stdout
   - Add basic logging to critical paths (ingestion, review)
4. Optionally add metrics (e.g., number of records processed/day)

**Tradeoff:** No APM (Datadog, New Relic) yet. Sentry for errors, platform logs for basics.

**Definition of Done:**
- [ ] Errors are logged to Sentry
- [ ] Can view logs in Render/Railway dashboard
- [ ] Health check endpoint works
- [ ] Can identify issues without SSH-ing into server

---

### Chunk 4.6: Backup & Data Safety

**Input:** PostgreSQL database on Render/Railway
**Output:** Automated backups, restore procedure documented

**Implementation Points:**

1. Render: automatic daily backups (built-in)
2. Test restore procedure:
   - Render provides restore to new DB
   - Document steps in README
3. No data deletion features yet—only soft deletes via status flags
4. Audit logs are immutable (never delete AuditLog records)

**Tradeoff:** Rely on platform backups for MVP. Add application-level export (CSV) later if needed.

**Definition of Done:**
- [ ] Automated backups are configured
- [ ] Restore procedure is documented
- [ ] No data is permanently deleted (only archived)
- [ ] Audit logs are never deleted

---

## APPENDIX: Execution Checklist

Use this to validate each chunk before moving to the next.

### Phase 1 Validation
- [ ] Phase 1.1: Models created, migrations work
- [ ] Phase 1.2: Can upload CSV without parsing
- [ ] Phase 1.3: Can parse CSV into rows
- [ ] Phase 1.4: Schema defined for 3+ fields
- [ ] Phase 1.5: Can normalize and validate
- [ ] Phase 1.6: Audit logs are created

### Phase 2 Validation
- [ ] Phase 2.1: API endpoints return JSON
- [ ] Phase 2.2: Analyst can approve/reject
- [ ] Phase 2.3: Can't access other tenant's data
- [ ] Phase 2.4: Ingestion workflow is end-to-end
- [ ] Phase 2.5: Can export approved records

### Phase 3 Validation
- [ ] Phase 3.1: React app calls backend API
- [ ] Phase 3.2: Can log in, token persists
- [ ] Phase 3.3: Can upload file and see progress
- [ ] Phase 3.4: Can approve/reject from dashboard
- [ ] Phase 3.5: Dashboard renders charts

### Phase 4 Validation
- [ ] Phase 4.1: Docker builds, compose works locally
- [ ] Phase 4.2: Env vars work, no secrets in code
- [ ] Phase 4.3: Migrations run, seed data loads
- [ ] Phase 4.4: App runs on Render/Railway
- [ ] Phase 4.5: Errors are logged, health check works
- [ ] Phase 4.6: Backups are configured

---

## Key Principles (Repeat Throughout)

1. **No Hallucination**: Each chunk is specific, defensible, and avoids generic patterns
2. **Data Lineage**: Track every record from raw upload to analyst approval
3. **Auditability**: Every change is logged, traceable, never deleted
4. **Multi-Tenancy**: Tenant ID is on every table, every query filters by it
5. **Realistic Validation**: Accept bad data, flag it, let analysts decide
6. **Simplicity**: No fancy async, no microservices, no over-engineering
7. **Incremental Deployment**: Each chunk works standalone; don't combine until ready

---

## Next Steps

1. Start with **Phase 1.1**: Create Django models
2. After Phase 1.1 works → Phase 1.2 (ingestion endpoint)
3. Continue sequentially
4. After each chunk, verify with the checklist above
5. Do not skip chunks (hallucination risk)
6. Do not combine chunks (makes debugging harder)

**Final Note**: This roadmap is meant to be fed to an AI assistant, chunk by chunk. Each chunk should be implementable in 30-60 minutes. If a chunk takes longer, split it further or ask clarifying questions about that chunk specifically.
