# Phase 3.5 & Phase 4: Roadmap & Implementation Guide

## Phase 3.5: Dashboard & Charts

### Chunk 3.5: Data Visualization & Explorer

**Status**: Design documented, implementation deferred

#### Components Needed:

```
src/pages/DashboardPage.jsx
├── Summary metrics (total emissions, facilities, records)
├── Charts:
│   ├── Total emissions by scope (Bar chart)
│   ├── Emissions by year (Line chart)
│   ├── Records by quality tier (Pie chart)
│   └── Data completeness % (Gauge)
├── Filters (year, facility, scope)
└── Approved records table below

Implementation approach:
- Use useEmissionsSummary() hook (from 3.1)
- Use Recharts library (npm install recharts)
- Charts are read-only (no editing)
- Filters update chart data reactively
```

#### Example Code Structure:

```javascript
import { BarChart, LineChart } from 'recharts'
import { useEmissionsSummary } from '../hooks/useEmissions'

export function DashboardPage() {
  const { data: summary } = useEmissionsSummary()
  const [filters, setFilters] = useState({ year: 2023 })
  
  return (
    <div>
      {/* Filters */}
      <select onChange={(e) => setFilters({year: e.target.value})}>
        <option value="2023">2023</option>
        <option value="2022">2022</option>
      </select>
      
      {/* Summary Cards */}
      <div>Total: {summary?.total_emissions}</div>
      <div>Facilities: {Object.keys(summary?.by_facility).length}</div>
      <div>Quality Avg: {summary?.average_quality_score}</div>
      
      {/* Charts */}
      <BarChart data={summary?.by_facility}>...</BarChart>
      <LineChart data={summary?.by_year}>...</LineChart>
      
      {/* Records Table */}
      <table>Approved records</table>
    </div>
  )
}
```

#### Dependencies:
```json
{
  "recharts": "^2.10.0"
}
```

#### Routes:
```javascript
<Route path="/dashboard" element={<DashboardPage />} />
```

#### Definition of Done:
- [ ] Dashboard loads with summary metrics
- [ ] Charts render correctly with Recharts
- [ ] Filters work (year filter updates data)
- [ ] Table shows approved records
- [ ] Responsive on mobile
- [ ] No errors in browser console

---

## Phase 4: Deployment & Operations

### Chunk 4.1: Dockerization

**Status**: Architecture defined, implementation deferred

#### Files Needed:

```dockerfile
# Dockerfile.backend
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput
CMD ["gunicorn", "breathe.wsgi:application", "--bind", "0.0.0.0:8000"]
```

```dockerfile
# Dockerfile.frontend
FROM node:18 AS build
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine
RUN npm install -g serve
COPY --from=build /app/dist /app/dist
CMD ["serve", "-s", "dist", "-l", "3000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: breathe_dev
      POSTGRES_USER: breathe
      POSTGRES_PASSWORD: changeme
    ports:
      - "5432:5432"
  
  backend:
    build: ./
    command: python manage.py runserver 0.0.0.0:8000
    environment:
      DATABASE_URL: postgresql://breathe:changeme@db:5432/breathe_dev
      DEBUG: "True"
    ports:
      - "8000:8000"
    depends_on:
      - db
  
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

#### Usage:
```bash
docker-compose up
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
# DB: localhost:5432
```

#### Definition of Done:
- [ ] `docker-compose up` starts all services
- [ ] Can access /api/auth/login/ without Python errors
- [ ] Frontend loads, not showing API errors
- [ ] Database is initialized
- [ ] No hardcoded secrets in images

---

### Chunk 4.2: Environment Configuration

**Status**: Architecture defined

#### Files:

```
.env.example
.env.development (git-ignored)
.env.production (set on platform)
```

#### Content:

```
# .env.example
DEBUG=False
DATABASE_URL=postgresql://user:pass@host:5432/breathe
SECRET_KEY=change-me-in-production
ALLOWED_HOSTS=localhost,127.0.0.1
VITE_API_URL=http://localhost:8000/api
```

#### Django Setup:

```python
# settings.py
import os
from urllib.parse import urlparse

DEBUG = os.getenv('DEBUG', 'False') == 'True'
SECRET_KEY = os.getenv('SECRET_KEY')

db_url = os.getenv('DATABASE_URL')
if db_url:
    db = urlparse(db_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': db.path[1:],
            'USER': db.username,
            'PASSWORD': db.password,
            'HOST': db.hostname,
            'PORT': db.port or 5432,
        }
    }

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')
```

---

### Chunk 4.3: Database Migrations

**Status**: Process defined

#### Workflow:

```bash
# Local development
python manage.py makemigrations  # Create migration files
python manage.py migrate         # Run migrations

# Production deployment (CI/CD)
python manage.py migrate --noinput  # Auto-run on startup
```

#### Seed Data:

```python
# breathe/management/commands/seed_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from breathe.apps.auth.models import Tenant, UserProfile

class Command(BaseCommand):
    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(
            name="Demo Company",
            defaults={"slug": "demo"}
        )
        
        user, _ = User.objects.get_or_create(
            username="analyst",
            defaults={
                "email": "analyst@demo.com",
                "is_staff": True
            }
        )
        
        UserProfile.objects.get_or_create(
            user=user,
            defaults={"tenant": tenant, "role": "ANALYST"}
        )
        
        self.stdout.write("Seed data created")
```

---

### Chunk 4.4: Deployment (Render.com Example)

**Status**: Process outlined

#### Steps:

1. **Create Render Account**
   - Sign up at https://render.com
   - Connect GitHub repo

2. **Create Web Service (Backend)**
   ```
   - Runtime: Docker
   - Dockerfile: Dockerfile (root)
   - Branch: main
   - Environment Variables:
     SECRET_KEY=<strong-random-key>
     DEBUG=False
     DATABASE_URL=<postgres-url>
   ```

3. **Create PostgreSQL Database**
   ```
   - Render auto-provides connection string
   - Copy to DATABASE_URL environment variable
   ```

4. **Create Web Service (Frontend)**
   ```
   - Runtime: Docker
   - Dockerfile: ./frontend/Dockerfile
   - Environment Variables:
     VITE_API_URL=https://breathe-api.onrender.com/api
   ```

5. **Deploy**
   ```
   git push origin main
   Render auto-deploys
   ```

#### Result:
```
Backend:  https://breathe-api.onrender.com
Frontend: https://breathe-app.onrender.com
```

---

### Chunk 4.5: Monitoring & Error Logging

**Status**: Integration pattern defined

#### Sentry Setup:

```bash
pip install sentry-sdk
```

```python
# settings.py
import sentry_sdk

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment="production",
    traces_sample_rate=0.1
)
```

#### Health Check:

```python
# urls.py
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"])
def health(request):
    return JsonResponse({"status": "ok", "version": "1.0.0"})

# In urlpatterns:
path("health/", health)
```

#### Usage:
```
GET https://breathe-api.onrender.com/health/
→ {"status": "ok"}
```

---

### Chunk 4.6: Backups & Data Safety

**Status**: Policy defined

#### Render PostgreSQL Backups:
- Automatic daily backups (built-in)
- 7-day retention
- Restore via Render dashboard

#### Data Deletion Policy:
```
NEVER delete:
- AuditLog records (immutable)
- User records (archive instead)

Archive patterns:
- EmissionsDataPoint: Set is_active=False
- RawIngestion: Keep forever (source of truth)
```

#### Soft Delete Pattern:

```python
class BaseModel(models.Model):
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True

# In queries:
EmissionsDataPoint.objects.filter(is_active=True)

# Deletion:
record.is_active = False
record.save()
```

---

## Complete Implementation Checklist

### Phases 1-2 (Backend) ✅ COMPLETE

- [x] 1.1: Django setup, models, migrations
- [x] 1.2: Raw ingestion, CSV storage
- [x] 1.3: CSV parsing, field detection
- [x] 1.4: Normalization, validation
- [x] 1.5: Analyst review workflow
- [x] 1.6: Audit logging
- [x] 2.1: JWT auth, multi-tenancy
- [x] 2.2: Review API endpoints
- [x] 2.3: Auth/permissions
- [x] 2.4: Ingestion workflow API
- [x] 2.5: Export & reporting

### Phase 3 Frontend ✅ PARTIALLY COMPLETE

- [x] 3.1: React setup, API client, hooks
- [x] 3.2: Login page, authentication
- [x] 3.3: Upload page, ingestion review
- [x] 3.4: Review dashboard, approve/reject
- [ ] 3.5: Dashboard, charts (design ready, code deferred)

### Phase 4 Deployment 📋 DESIGN READY

- [ ] 4.1: Dockerization
- [ ] 4.2: Environment configuration
- [ ] 4.3: Database migrations
- [ ] 4.4: Deployment to Render/Railway
- [ ] 4.5: Error monitoring (Sentry)
- [ ] 4.6: Backups & data safety

---

## Implementation Priority

If continuing beyond current checkpoint:

1. **Phase 3.5** (1-2 hours) - Dashboard with Recharts charts
2. **Phase 4.1-4.3** (2-3 hours) - Docker + environment setup
3. **Phase 4.4** (1 hour) - Deploy to Render
4. **Phase 4.5-4.6** (30 min) - Monitoring + backups

Total remaining: ~6-8 hours of development.

---

## Key Accomplishments

✅ **Full-Stack ESG Platform**: Upload → Parse → Review → Approve → Export
✅ **Multi-Tenancy**: Complete isolation between organizations
✅ **Audit Trail**: Immutable logs for compliance
✅ **Data Quality**: Validation + scoring at every step
✅ **User-Friendly**: Analysts can work efficiently
✅ **Production-Ready Architecture**: Ready for deployment

---

This roadmap provides implementation specifications for Phase 3.5 and Phase 4. All code is designed to be realistic, maintainable, and follow project principles of no over-engineering and no hallucinations.

