# Chunk 4.3: Database Migrations & Seed Data - Implementation Complete

**Status**: ✅ COMPLETE

## Overview

Phase 4.3 establishes the database migration workflow and provides a seed data command for development and testing. All database schema changes are tracked in version control via migration files.

## Files Implemented

### 1. breathe/management/commands/seed_data.py
**Location**: `breathe/management/commands/seed_data.py`

**Purpose**: Management command to populate database with demo data

**Features**:
- Creates demo tenant ("Demo Company")
- Creates analyst user (analyst@demo.com)
- Creates data provider user (provider@demo.com)
- Links users to tenant via UserProfile
- Prints setup summary with credentials
- Idempotent (safe to run multiple times)

**Database State**:
Creates:
1. Tenant: "Demo Company" (slug: "demo")
2. Users: analyst@demo.com, provider@demo.com
3. UserProfiles: Links each user to tenant with appropriate role

**Usage**:
```bash
# Local development
python manage.py seed_data

# In Docker
docker-compose exec backend python manage.py seed_data

# Output
Starting data seed...
✓ Created tenant: Demo Company
✓ Created user: analyst@demo.com
  Note: Default password is "demo123456" - change immediately!
✓ Created user profile: analyst@demo.com -> Demo Company
✓ Created user: provider@demo.com
✓ Created provider profile
✓ Data seed complete!

Demo Credentials:
  Analyst Email: analyst@demo.com
  Analyst Password: demo123456
  Provider Email: provider@demo.com
  Provider Password: demo123456
  Tenant: Demo Company

⚠️  Change these credentials immediately in production!
```

**Safety Features**:
- Idempotent: Won't fail if data already exists
- Defaults: Uses Django's set_password() for secure hashing
- Messages: Clear output about what was created vs. existing
- Role-Based: Different roles for analyst and provider users

### 2. breathe/management/__init__.py
**Location**: `breathe/management/__init__.py`

**Purpose**: Makes management directory a Python package

### 3. breathe/management/commands/__init__.py
**Location**: `breathe/management/commands/__init__.py`

**Purpose**: Makes commands directory a Python package

## Django Migrations Workflow

### Creating Migrations

```bash
# After modifying models in any app (breathe/apps/*/models.py):
python manage.py makemigrations

# Review generated migration files
ls breathe/apps/*/migrations/

# Check migration SQL
python manage.py sqlmigrate <app> <migration_number>
```

### Applying Migrations

```bash
# Apply all pending migrations
python manage.py migrate

# Specify specific app
python manage.py migrate <app>

# Rollback to specific migration
python manage.py migrate <app> <migration_number>
```

### Migration File Structure

```
breathe/apps/<app>/migrations/
├── 0001_initial.py
├── 0002_add_field_xyz.py
├── 0003_remove_deprecated_field.py
└── __init__.py
```

Each migration file:
- Is numbered sequentially
- Contains dependencies (previous migrations it depends on)
- Is tracked in Git
- Can be rolled back or reapplied

**Example migration**:
```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('ingest', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='rawingestion',
            name='data_hash',
            field=models.CharField(max_length=64, null=True),
        ),
    ]
```

## Deployment Workflow

### Local Development

```bash
# 1. Create .env.local with database credentials
cp .env.example .env.local

# 2. Run migrations
python manage.py migrate

# 3. Seed demo data
python manage.py seed_data

# 4. Start development server
python manage.py runserver
```

### Docker Development

```bash
# 1. Start services (migrations run automatically)
docker-compose up

# 2. Seed demo data
docker-compose exec backend python manage.py seed_data

# 3. App is ready at http://localhost:3000
```

### Production Deployment (Render)

```bash
# 1. Push code to main branch
git push origin main

# 2. Render automatically:
#    a. Builds Docker image
#    b. Runs migrations (via docker-compose.yml or startup script)
#    c. Deploys new version

# 3. Verify migrations completed
#    (Check Render logs for "Applied X migrations")

# 4. Seed data (if first deployment)
#    Run once via Render dashboard > Shell
#    Command: python manage.py seed_data
```

## Migration Best Practices

### ✅ DO

- Run `makemigrations` after every model change
- Commit migration files to Git
- Test migrations locally before pushing
- Write descriptive migration names
- Run migrations in order (Django tracks this)
- Keep migrations small and focused

### ❌ DON'T

- Manually edit migration files (regenerate instead)
- Delete migration files (create a new migration to undo)
- Run migrations without testing
- Skip migrations in deployment
- Mix multiple unrelated changes in one migration

## Testing Migrations

### Dry Run (Check What Would Happen)

```bash
# Show pending migrations without applying
python manage.py showmigrations

# Show SQL that will be executed
python manage.py sqlmigrate ingest 0001
```

### Test Rollback

```bash
# Apply migrations
python manage.py migrate

# Rollback one migration
python manage.py migrate ingest 0001

# Reapply
python manage.py migrate ingest
```

### Fresh Database (Testing)

```bash
# Delete all tables and reapply from scratch
python manage.py migrate breathe zero  # Unapply all
python manage.py migrate               # Reapply all
```

## Troubleshooting Migrations

### Migration Conflicts (Multiple Developers)

```bash
# If two branches create conflicting migrations:
# 1. Delete conflicting migration from newer branch
# 2. Create merge migration:
python manage.py makemigrations --merge

# 3. Test thoroughly
python manage.py migrate
```

### Database Out of Sync

```bash
# Check migration status
python manage.py showmigrations

# If database is ahead of code:
# Manually delete unexpected tables, or
# Create new migration to document state:
python manage.py makemigrations --empty ingest --name fix_database_state

# Edit the migration to describe actual state
```

### Cannot Undo Migration

```bash
# Don't delete migration file, instead:
python manage.py makemigrations --name revert_xyz_change

# Edit new migration to reverse previous one
# (Django provides useful reverse() methods)
```

## Seed Data Strategy

### When to Use Seed Data

- ✅ Development: Populate test data automatically
- ✅ Staging: Create demo accounts for testing
- ✅ CI/CD: Initialize test database
- ❌ Production: Don't seed automatically (manual control)

### Extending Seed Data

Modify `seed_data.py` to add more demo data:

```python
# Add sample emissions records
from breathe.apps.emissions.models import EmissionsDataPoint

record, created = EmissionsDataPoint.objects.get_or_create(
    tenant=tenant,
    facility_name='Plant A',
    reporting_year=2023,
    defaults={
        'scope_1_emissions': 1500.5,
        'scope_2_emissions': 2300.0,
        'scope_3_emissions': 0.0,
        'is_valid': True,
        'data_quality_score': 85
    }
)
```

## Verification Checklist

- [x] Migrations directory exists in all apps
- [x] seed_data.py management command created
- [x] Can run `python manage.py migrate` without errors
- [x] Can run `python manage.py seed_data` without errors
- [x] Demo users are created with correct roles
- [x] Users are linked to demo tenant
- [x] Demo credentials work for login
- [x] Database schema matches current models
- [x] All migrations are committed to Git
- [x] `.gitignore` excludes local database files
- [x] Docker Compose runs migrations automatically
- [x] Rollback works (can revert migrations)

## File Locations Summary

```
breathe/
├── management/
│   ├── __init__.py
│   └── commands/
│       ├── __init__.py
│       └── seed_data.py
├── apps/
│   ├── ingest/
│   │   ├── migrations/
│   │   │   ├── 0001_initial.py
│   │   │   └── __init__.py
│   │   └── models.py
│   ├── emissions/
│   │   └── migrations/
│   ├── review/
│   │   └── migrations/
│   ├── audit/
│   │   └── migrations/
│   └── tenants/
│       └── migrations/
└── settings.py
```

## Next Steps

Phase 4.4 (Deployment) uses this migration workflow:
- Container startup script: `docker-compose run backend python manage.py migrate`
- Ensures database is initialized before app starts
- Supports rolling updates with zero downtime

---

**Phase 4.3 is production-ready. Migrations are tracked, seed data is automated, and deployment handles initialization securely.**
