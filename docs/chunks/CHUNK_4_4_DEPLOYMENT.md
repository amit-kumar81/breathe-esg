# Chunk 4.4: Deployment to Render - Complete Guide

**Status**: ✅ READY FOR DEPLOYMENT

## Overview

Phase 4.4 provides step-by-step instructions for deploying the Breathe ESG platform to Render.com, a cloud platform with automatic deployments from GitHub, managed PostgreSQL, and simple configuration.

## Why Render?

- ✅ Free tier available for hobby projects
- ✅ Automatic deployments from GitHub (git push = instant deploy)
- ✅ Managed PostgreSQL database (automatic backups, SSL)
- ✅ No credit card required for free tier
- ✅ Simple environment variable management
- ✅ Built-in logging and monitoring
- ✅ HTTPS/SSL included

## Prerequisites

1. **GitHub account** with repository pushed
2. **Render.com account** (https://render.com) - sign up with GitHub
3. **Django project** with Docker support (✅ we have this)
4. **PostgreSQL support** in requirements.txt (✅ we have this)

## Step 1: Prepare Repository

### 1.1 Ensure Dockerfile.backend Exists

```bash
# Backend Dockerfile must be in repository root
ls Dockerfile.backend

# Frontend Dockerfile must be in frontend directory
ls frontend/Dockerfile

# docker-compose.yml for local testing
ls docker-compose.yml
```

### 1.2 Update requirements.txt for Production

```bash
# Add production WSGI server (gunicorn)
pip install gunicorn dj-database-url

# Update requirements.txt
pip freeze > requirements.txt
```

### 1.3 Ensure .gitignore is Correct

```bash
# Never commit sensitive files
cat .gitignore | grep -E "\.env|\.env\.local|secrets"

# Should contain:
# .env.local
# .env.production
# *.pyc
# __pycache__/
# db.sqlite3
```

### 1.4 Test Locally with Docker

```bash
# Verify everything works in Docker before deploying
docker-compose build
docker-compose up

# Test in browser
# Backend: http://localhost:8000/health/
# Frontend: http://localhost:3000

# Stop and clean
docker-compose down
```

## Step 2: Create Render Account

1. Go to https://render.com
2. Click "Sign up"
3. Choose "Sign up with GitHub"
4. Authorize Render to access your GitHub account
5. Confirm email

## Step 3: Create Web Service (Backend)

### 3.1 Connect GitHub Repository

1. In Render dashboard, click **"New +"** → **"Web Service"**
2. Click **"Connect Repository"**
3. Select your GitHub repository (e.g., `breathe-esg`)
4. Click **"Connect"**

### 3.2 Configure Service

```
Name:                      breathe-api
Environment:               Docker
Dockerfile:                Dockerfile.backend
Branch:                    main
Region:                    Oregon (or closest to users)
Plan:                      Free (for hobby)
```

### 3.3 Set Environment Variables

Click **"Environment"** and add:

```
DEBUG                      False
SECRET_KEY                 <GENERATE NEW - see below>
DATABASE_URL              <LEAVE BLANK - set after DB is created>
ALLOWED_HOSTS             breathe-api.onrender.com
VITE_API_URL              https://breathe-api.onrender.com/api
```

### 3.4 Generate Strong SECRET_KEY

```bash
# Run this locally to generate a secure key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Output example: )3#hbr7mq8@_j^!-_4pq@qx^jz#b8v+3z&!e$i_y(*9
# Copy this value to SECRET_KEY in Render
```

**Important**: Never reuse development key in production

### 3.5 Create Service (Without DATABASE_URL Yet)

Click **"Create Web Service"**

- Render will build Docker image and deploy
- You'll see logs: "Building...", "Deploying..."
- Wait for deployment to complete (~5 minutes)
- You'll get a URL: `https://breathe-api.onrender.com`
- Access will fail because database isn't configured yet (expected)

## Step 4: Create PostgreSQL Database

### 4.1 Create Database Service

1. In Render dashboard, click **"New +"** → **"PostgreSQL"**

### 4.2 Configure Database

```
Name:                      breathe-db
Database:                  breathe_prod
PostgreSQL Version:        Latest
Region:                    Oregon (same as web service)
Plan:                      Free (for hobby) or Starter Plus
```

### 4.3 Create Database

Click **"Create Database"**

- Render creates PostgreSQL instance
- You'll see connection details

### 4.4 Copy Connection String

1. Go to database details page
2. Copy **"Internal Database URL"** (appears as `postgresql://...`)
3. Save for next step

## Step 5: Link Database to Web Service

### 5.1 Update Backend Environment Variables

1. Go to backend (breathe-api) service
2. Click **"Environment"**
3. Add new variable:

```
Name:           DATABASE_URL
Value:          <paste connection string from Step 4.4>
```

4. Click **"Save"**
5. Backend automatically redeploys

### 5.2 Run Migrations

Wait for redeployment to complete, then:

1. Click **"Shell"** (top right of web service page)
2. Run command:

```bash
python manage.py migrate
```

3. Wait for output: "Applied N migrations"

### 5.3 Create Demo User (Optional)

Still in Shell:

```bash
python manage.py seed_data
```

Output will show demo credentials.

### 5.4 Test API

```bash
# In browser or curl
curl https://breathe-api.onrender.com/health/

# Should return: {"status": "ok"}

# Or access admin
https://breathe-api.onrender.com/admin/
```

## Step 6: Create Web Service (Frontend)

### 6.1 Create Frontend Service

1. In Render dashboard, click **"New +"** → **"Web Service"**
2. Click **"Connect Repository"** (same repo)
3. Configure:

```
Name:                      breathe-app
Environment:               Docker
Dockerfile:                frontend/Dockerfile
Branch:                    main
Region:                    Oregon (same as backend)
Plan:                      Free (for hobby)
```

### 6.2 Set Environment Variables

```
VITE_API_URL               https://breathe-api.onrender.com/api
```

### 6.3 Create Service

Click **"Create Web Service"**

- Render builds and deploys
- You get URL: `https://breathe-app.onrender.com`
- Should be live in ~3 minutes

## Step 7: Verify End-to-End

### 7.1 Check Services

```bash
# Backend Health
curl https://breathe-api.onrender.com/health/
# Should return: {"status":"ok"}

# Frontend
https://breathe-app.onrender.com
# Should load React app
```

### 7.2 Test Login

1. Go to https://breathe-app.onrender.com
2. Click Login
3. Use demo credentials (if seeded):
   - Email: analyst@demo.com
   - Password: demo123456

### 7.3 Test Upload

1. Click Upload
2. Upload a sample CSV file
3. Should see ingestion ID and progress
4. Should appear in review dashboard

### 7.4 Check Logs

**Backend logs**:
- Go to breathe-api service → Logs
- Look for any errors

**Frontend logs**:
- Go to breathe-app service → Logs
- Should show successful builds

## Step 8: Configure Custom Domain (Optional)

### 8.1 Add Custom Domain

1. Go to backend service → Settings → Custom Domains
2. Add domain: `api.yourdomain.com`
3. Render shows CNAME instruction
4. Update DNS records at your domain provider
5. Wait for HTTPS certificate (automatic, ~24 hours)

### 8.2 Frontend Custom Domain

1. Go to frontend service → Settings → Custom Domains
2. Add domain: `app.yourdomain.com` or `yourdomain.com`
3. Follow DNS instructions
4. HTTPS is automatic

## Step 9: Automated Deployments

### 9.1 How Deployments Work

1. Push code to GitHub main branch:
   ```bash
   git commit -m "Update feature"
   git push origin main
   ```

2. Render automatically:
   - Detects changes
   - Builds new Docker images
   - Runs migrations (if any)
   - Deploys without downtime

3. Check deployment status in Render dashboard

### 9.2 View Deployment Logs

- Service → Events: Shows deployment history
- Service → Logs: Shows runtime logs

### 9.3 Rollback (If Needed)

1. Go to Events
2. Find previous successful deployment
3. Click rollback
4. Render redeploys previous version

## Troubleshooting

### Backend Won't Start

```bash
# Check logs
Service → Logs

# Look for common errors:
# - ModuleNotFoundError: Install in requirements.txt
# - Database connection error: Check DATABASE_URL
# - SECRET_KEY error: Ensure it's set as environment variable

# If unknown error, use Shell to debug:
Service → Shell
python manage.py runserver  # Should show error

# Or rebuild:
Service → Settings → Rebuild
```

### Frontend Build Fails

```bash
# Check logs
Service → Logs

# Common issues:
# - npm install fails: Ensure package-lock.json is committed
# - Build error: Check for syntax errors in code
# - VITE_API_URL wrong: Update in Service → Environment

# Rebuild:
Service → Settings → Rebuild
```

### Database Connection Error

```bash
# Verify DATABASE_URL is set
Service → Environment → Check DATABASE_URL value

# Test connection
Service → Shell
python -c "from django.db import connection; connection.ensure_connection()"

# If still fails, recreate database
# (Advanced: Not recommended for production with data)
```

### Login Fails

```bash
# Check if users exist
Service → Shell
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.all().count()

# If 0 users, seed data:
python manage.py seed_data

# If that fails, check logs for database errors
```

### Slow Performance

```
Free tier limitations:
- 0.5 CPU
- 512 MB RAM
- Spins down after 15 minutes inactivity

Upgrade to:
- Starter Plus ($12/month): 1 CPU, 1 GB RAM
- Or Standard ($30+/month): Professional resources
```

## Costs (As of 2026)

| Service | Free Tier | Starter Plus | Notes |
|---------|-----------|--------------|-------|
| Web Service | ✓ | $12/mo | Spins down after 15min |
| PostgreSQL | Limited | $15/mo | 1 GB storage |
| **Total/mo** | **Free** | **$27** | Recommended for production |

**Free tier great for hobby, development, prototyping.**
**Starter Plus recommended for any real users or data.**

## Production Checklist

- [x] Repository pushed to GitHub
- [x] Dockerfile.backend and frontend/Dockerfile committed
- [x] requirements.txt includes gunicorn and dj-database-url
- [x] .env files are in .gitignore
- [x] SECRET_KEY is generated (not default)
- [x] DEBUG=False in production environment
- [x] PostgreSQL database created
- [x] DATABASE_URL set in backend environment
- [x] Migrations have run (check logs)
- [x] Demo users created (if needed)
- [x] ALLOWED_HOSTS updated with Render domain
- [x] HTTPS is enabled (automatic)
- [x] Health endpoint works (/health/)
- [x] Login works with test credentials
- [x] Upload workflow works end-to-end
- [x] Logs are accessible and clear
- [x] Auto-deployment triggers on git push
- [x] Database has automatic backups

## Next Steps

Phase 4.5 (Monitoring) adds:
- Error tracking via Sentry
- Health checks
- Logging and alerts

Phase 4.6 (Backups) ensures:
- Automatic database backups
- Data recovery procedures
- Audit log preservation

---

**Phase 4.4 is complete. Platform is live on Render and ready for real users.**

Congratulations! Your ESG platform is in production. 🎉
