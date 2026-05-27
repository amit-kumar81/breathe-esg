# BreatheESG Platform - Implementation Chunks Documentation

This folder contains comprehensive documentation for each implementation chunk of the ESG emissions data ingestion and analyst review platform.

## Structure

Each chunk has three files:

1. **CHUNK_X_EXPLANATION.md** - Comprehensive explanation
   - Architecture decisions and tradeoffs
   - Why each approach was chosen vs. alternatives
   - Implementation walkthrough
   - 10+ interview Q&A pairs with detailed answers
   - Edge cases and gotchas

2. **CHUNK_X_INTEGRATION_GUIDE.md** - Testing and integration
   - Setup instructions
   - 7-10 complete test cases with expected responses
   - Manual testing with curl commands
   - Verification steps

3. **CHUNK_X_SUMMARY.md** - Quick reference
   - What was built
   - Key architectural decisions
   - File changes
   - Success criteria

## Completed Chunks

### ✅ Chunk 1.1: Django Project Setup + Database Schema
- Django 5.2 with PostgreSQL
- Tenant model (multi-tenancy)
- DataSource, RawIngestion, ParsedRecord models
- EmissionsDataPoint model foundation

### ✅ Chunk 1.2: Raw Data Ingestion Endpoint
- POST /api/ingest/upload/ endpoint
- SHA256 hashing for idempotency
- File validation (CSV, UTF-8, <10MB)
- RawIngestion creation (stores raw_csv_content)

### ✅ Chunk 1.3: CSV Parser & ParsedRecord Generation
- POST /api/ingest/{id}/parse/ endpoint
- CSV dialect detection (comma, semicolon, tab, pipe)
- Empty row handling
- ParsedRecord creation (structured, unvalidated)

### ✅ Chunk 1.4: Schema Definition & Normalization Rules
- Standard field definitions (facility_name, scope_1/2/3_emissions, year)
- Field validators (required, type, range)
- Field mapping (CSV columns → standard fields)
- NormalizedRecord model with is_valid flag
- Data quality score calculation (0-100)
- POST /api/ingest/{id}/normalize/ endpoint

## In Progress / Upcoming

### 🔄 Chunk 1.5: Analyst Review & Approval Workflow
- ReviewTask model
- Approval/rejection endpoints
- EmissionsDataPoint creation
- Dashboard for analyst

### 📋 Chunk 2.1: Authentication & Multi-Tenancy (Real)
- JWT auth implementation
- User model with tenant association
- Proper tenant isolation (not placeholders)

### 📋 Chunk 2.2: Advanced Filtering & Querying
- Emissions data point filtering
- Aggregation by facility, scope, year
- Export functionality

### 📋 Chunk 2.3: Frontend (React)
- File upload interface
- Review dashboard
- Analytics dashboard

## Design Principles

All implementations follow these principles:

1. **Avoid Hallucinations**: Every design choice is explained with WHY
2. **Realistic Approach**: No over-engineering, MVP-focused
3. **Single Source of Truth**: Design to eliminate data loss risks
4. **Pure Functions**: Testable, deterministic business logic
5. **Separation of Concerns**: Each layer has one responsibility
6. **Comprehensive Documentation**: 700+ lines per chunk with 10+ Q&A
7. **Complete Testing**: 7-10 integration tests per chunk
8. **Hybrid Design**: Relational + JSONB for consistency + flexibility

## Key Concepts

### Data Flow

```
CSV File
  ↓ [Chunk 1.2: Upload]
RawIngestion (raw_csv_content = original text, single source of truth)
  ↓ [Chunk 1.3: Parse with dialect detection]
ParsedRecord (structured dict, no validation)
  ↓ [Chunk 1.4: Normalize & validate]
NormalizedRecord (validated, is_valid flag, quality_score)
  ↓ [Chunk 1.5: Analyst review & approval]
EmissionsDataPoint (approved, ready for analytics)
```

### Architecture Decisions

- **Pure Relational Storage** (Option 1): Store raw_csv_content (TEXT) as single source of truth, parse on-demand
- **Hybrid Data Model**: Relational fields (indexed, queryable) + JSONB (flexible, audit trail)
- **Deterministic Processing**: Same input = same output every time (idempotent)
- **Error Isolation**: Collect all validation errors, continue processing
- **Transparent Scoring**: Data quality calculated, not subjective

## Testing Strategy

Each chunk includes:
- 7-10 integration tests with manual steps
- Edge cases and error scenarios
- Success criteria checklist
- Django admin verification steps

Run tests with:
```bash
# Setup
docker-compose exec backend python manage.py shell

# Run manual tests
curl -X POST http://localhost:8000/api/ingest/upload/ ...
curl -X POST http://localhost:8000/api/ingest/{id}/parse/ ...
curl -X POST http://localhost:8000/api/ingest/{id}/normalize/ ...
curl -X POST http://localhost:8000/api/ingest/{id}/approve/ ...  # Chunk 1.5
```

## Next Steps

1. Complete Chunk 1.5: Analyst Review & Approval
2. Run all integration tests
3. Implement Chunk 2.1: Real authentication
4. Build Chunk 2.3: React frontend

---

**Version**: May 2026
**Status**: Chunk 1.5 in progress
**Owner**: Development team
