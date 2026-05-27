# Chunk 2.1: Django REST Framework Setup & Serializers — Summary

## What Was Built

**Chunk 2.1** exposes the Phase 1 data models as clean REST API endpoints using Django REST Framework. This layer transforms Django ORM queries into JSON responses that the frontend (React) can consume.

### Core Components

1. **Serializers** (emissions/serializers.py, ingest/serializers_new.py)
   - **EmissionsDataPointListSerializer**: Lightweight for list views (no audit trail)
   - **EmissionsDataPointDetailSerializer**: Full data for detail views (includes audit trail)
   - **AuditLogSerializer**: Serializes audit trail entries
   - **NormalizedRecordSerializer**: Serializes ingest workflow data
   
2. **Filters** (emissions/filters.py)
   - Filter by: year, review_status, facility_name, data_source
   - Range filters: quality_score_min, quality_score_max
   - Search support: icontains search on facility_name

3. **ViewSet** (emissions/views.py)
   - **EmissionsDataPointViewSet**: CRUD for EmissionsDataPoint (read-only)
   - Custom actions: `/audit/`, `/summary/`
   - Filtering, searching, ordering, pagination built-in

4. **URL Routing** (emissions/urls.py)
   - Uses DRF's DefaultRouter for automatic route generation
   - Generates: list, detail, and custom action endpoints

---

## API Endpoints

### List with Filtering
```
GET /api/emissions/
?year=2023
&review_status=PENDING
&quality_score_min=80
&facility_name=plant
&search=alpha
&ordering=-created_at
&page=1
```

**Response** (paginated):
```json
{
  "count": 95,
  "next": "http://.../api/emissions/?page=2",
  "previous": null,
  "results": [
    {
      "id": "emission-uuid",
      "facility_name": "Plant A",
      "scope_1_emissions": 100.5,
      "scope_2_emissions": 50.0,
      "scope_3_emissions": 10.0,
      "year": 2023,
      "methodology": "GHG Protocol",
      "review_status": "PENDING",
      "data_quality_score": 85,
      "validation_error_count": 2,
      "data_quality_flag_count": 1,
      "created_at": "2024-05-27T10:00:00Z"
    }
  ]
}
```

### Detail with Audit Trail
```
GET /api/emissions/{id}/
```

**Response**:
```json
{
  "id": "emission-uuid",
  "facility_name": "Plant A",
  "scope_1_emissions": 100.5,
  "validation_errors": [
    {"field": "methodology", "message": "Missing", ...}
  ],
  "data_quality_flags": [...],
  "data_quality_score": 85,
  "review_status": "PENDING",
  "data_source_name": "Q1_2023_emissions.csv",
  "reviewed_at": null,
  "reviewer_notes": null,
  "created_at": "2024-05-27T10:00:00Z",
  "updated_at": "2024-05-27T11:00:00Z",
  "recent_changes": [
    {
      "id": "audit-uuid",
      "action": "CREATE",
      "timestamp": "2024-05-27T10:00:00Z",
      "user_name": "analyst1@example.com",
      "ip_address": "192.168.1.1",
      "change_summary": {"new_values": {...}}
    }
  ]
}
```

### Audit Trail
```
GET /api/emissions/{id}/audit/
```

**Response**:
```json
{
  "emissions_data_point_id": "emission-uuid",
  "facility_name": "Plant A",
  "total_changes": 3,
  "audit_trail": [
    {
      "id": "audit-uuid-1",
      "action": "CREATE",
      "timestamp": "2024-05-27T10:00:00Z",
      "user_name": "analyst1@example.com",
      "change_summary": {"new_values": {...}}
    },
    {
      "id": "audit-uuid-2",
      "action": "UPDATE",
      "timestamp": "2024-05-27T11:00:00Z",
      "user_name": "analyst1@example.com",
      "change_summary": {"old_values": {...}, "new_values": {...}}
    }
  ]
}
```

### Summary Stats
```
GET /api/emissions/summary/
```

**Response**:
```json
{
  "total_records": 500,
  "by_status": {
    "PENDING": 50,
    "APPROVED": 400,
    "REJECTED": 50
  },
  "by_data_quality": {
    "0-20": 10,
    "20-40": 20,
    "40-60": 30,
    "60-80": 100,
    "80-100": 340
  },
  "by_year": {
    "2023": 200,
    "2024": 300
  },
  "average_quality_score": 75.5
}
```

---

## Key Architectural Decisions

### 1. Flattened Serializers
- ✅ **Chosen**: Flatten normalized_values for easier frontend consumption
- ❌ Rejected: Return raw nested JSON (harder for frontend)

### 2. Separate List vs. Detail Serializers
- ✅ **Chosen**: Lightweight list (no audit trail), detailed retrieve (includes audit trail)
- ❌ Rejected: Single serializer (performance issue)

### 3. DjangoFilterBackend for Filtering
- ✅ **Chosen**: Reusable FilterSet class (safe, extensible)
- ❌ Rejected: Manual query parameter parsing (error-prone)

### 4. ReadOnlyModelViewSet (GET Only)
- ✅ **Chosen**: No POST/PUT/DELETE via API (updates via pipeline)
- ❌ Rejected: Full ModelViewSet (bypasses validation, audit)

### 5. Custom Actions for Detail Routes
- ✅ **Chosen**: @action decorator for /audit/ and /summary/
- ❌ Rejected: Separate ViewSets (complex routing)

### 6. Default Ordering (Newest First)
- ✅ **Chosen**: Default order by -created_at (most recent)
- ❌ Rejected: Alphabetical or random (less intuitive)

---

## File Structure

```
breathe/apps/emissions/
├── serializers.py          # EmissionsDataPoint serializers
├── filters.py              # FilterSet for filtering
├── views.py                # ViewSet and custom actions
├── urls.py                 # Router and URL registration
└── models.py               # (from Phase 1)

breathe/apps/ingest/
├── serializers_new.py      # RawIngestion, ParsedRecord serializers
└── models.py               # (from Phase 1)
```

---

## Database Query Examples

### List with Filtering

```python
# QuerySet before serialization
EmissionsDataPoint.objects.filter(
    normalized_values__year=2023,
    review_status='PENDING',
    data_quality_score__gte=80
).order_by('-created_at')
```

### Detail with Related Data

```python
emission = EmissionsDataPoint.objects.get(id=id)
audits = AuditLog.objects.filter(object_id=str(emission.id)).order_by('-timestamp')
# Serializer includes: recent_changes = AuditLogSerializer(audits, many=True).data
```

---

## Testing Coverage

10 integration tests provided in CHUNK_2_1_INTEGRATION_GUIDE.md:

1. ✅ List endpoint returns paginated results
2. ✅ Detail endpoint includes audit trail
3. ✅ Filter by year works
4. ✅ Filter by review_status works
5. ✅ Search by facility_name works
6. ✅ Filter by data quality score (range) works
7. ✅ Pagination works (pages, next/prev links)
8. ✅ Audit trail endpoint returns change history
9. ✅ Summary stats endpoint returns statistics
10. ✅ Combined filters work together

---

## Success Criteria

✅ Can list EmissionsDataPoints as JSON with pagination
✅ Detail endpoint includes full audit trail
✅ Filtering by year, review_status, facility_name works
✅ Search functionality works
✅ Data quality score range filtering works
✅ Ordering/sorting works
✅ Serializer flattens normalized_values (no deep nesting)
✅ List serializer is lightweight (no heavy audit trail)
✅ Detail serializer includes all related data
✅ Custom endpoints (/audit/, /summary/) work
✅ API returns 200 for valid requests, 400 for bad filters

---

## Next Steps (Chunk 2.2)

**Chunk 2.2**: Analyst Review Workflow API
- Create ReviewTask model and endpoints
- Endpoints to approve/reject EmissionsDataPoints
- POST /api/review/{id}/approve/
- POST /api/review/{id}/reject/

---

## Key Principles

1. **Flattening**: Frontend gets flat data, not nested JSON
2. **Separation**: List vs. Detail for performance
3. **Safety**: ReadOnly (no direct updates via API)
4. **Filtering**: Powerful filtering without custom code
5. **Audit Trail**: Always available for compliance
6. **Pagination**: Large datasets handled efficiently
7. **Search**: Natural text search on facility name

---

## Configuration (settings.py)

```python
INSTALLED_APPS = [
    'rest_framework',
    'django_filters',
]

REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}
```

---

**Version**: May 2026
**Status**: Chunk 2.1 complete
**Next**: Chunk 2.2 (Analyst Review Workflow API)

