# Chunk 2.1: Django REST Framework Setup & Serializers — Comprehensive Explanation

## Overview

Chunk 2.1 exposes the Phase 1 data models as clean REST API endpoints. This layer transforms Django ORM queries into JSON responses that the frontend (React) can consume. The key principle is **flattening nested data** so the frontend doesn't need to drill into `normalized_values.facility_name`; it gets `facility_name` directly.

**Goal**: Build API endpoints that serialize data cleanly, with filtering, pagination, and related data included.

## Why Django REST Framework? (Architectural Rationale)

### The Problem (No API Yet)

In Chunks 1.1-1.6, we built the data models and audit logging. But they only exist in the database. There's no way for a frontend or external system to read/interact with the data.

**Without DRF**:
- Frontend can't fetch data
- No standard JSON serialization
- Each endpoint is custom-built
- No built-in filtering, pagination, validation

**With DRF**:
- Standard REST conventions (GET /api/emissions/, GET /api/emissions/{id}/)
- Automatic serialization (model → JSON)
- Built-in filtering, pagination, search
- Reusable serializers and viewsets

### Why Not GraphQL or Raw Django Views?

**DRF (chosen)**: 
- ✅ Fast to implement, great for MVP
- ✅ Strong community (widely documented)
- ✅ Easy filtering (DjangoFilterBackend)
- ✅ Built-in pagination
- ❌ Less flexible than GraphQL (but simpler)

**GraphQL (alternative)**:
- ✅ Clients specify exactly what fields they want
- ✅ Single query instead of multiple endpoints
- ❌ Overkill for MVP (slower to implement)
- ❌ Harder to cache

**Raw Django Views (alternative)**:
- ✅ Full control
- ❌ No reusable patterns
- ❌ Manual pagination/filtering
- ❌ More boilerplate

**Decision**: DRF for MVP. Migrate to GraphQL if needed later.

---

## Key Architectural Decisions

### 1. Flattened Serializers (✅ Chosen)

**Decision**: In serializers, flatten nested JSONB fields (normalized_values) so frontend gets simple dicts.

**Why**:
- **Frontend-friendly**: React components expect flat data: `{facility_name: "Plant A", scope_1_emissions: 100}`
- **Less nesting**: No need for `data.normalized_values.facility_name`
- **Type safety**: Declare exact field names in serializer

**Example**:
```python
# Model (Django)
class EmissionsDataPoint(models.Model):
    normalized_values = JSONField()  # {"facility_name": "...", "scope_1_emissions": ...}

# Serializer (DRF) - FLATTENS it
class EmissionsDataPointSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source='normalized_values.facility_name')
    scope_1_emissions = serializers.FloatField(source='normalized_values.scope_1_emissions')

# API Response (JSON)
{
    "id": "...",
    "facility_name": "Plant A",  # No nesting!
    "scope_1_emissions": 100.5,
    ...
}
```

**Rejected Alternatives**:
- ❌ Return raw normalized_values: `{"normalized_values": {facility_name: ...}}` (harder for frontend)
- ❌ Custom JSON encoder: Less explicit, harder to validate

### 2. Separate List vs. Detail Serializers (✅ Chosen)

**Decision**: Use lightweight serializer for list (EmissionsDataPointListSerializer) and detailed serializer for retrieve (EmissionsDataPointDetailSerializer).

**Why**:
- **Performance**: List endpoint doesn't load full audit trail (heavy)
- **Clarity**: Different data for different use cases
- **Efficiency**: Frontend dashboard gets counts; detail view gets full history

**How It Works**:
```python
class EmissionsDataPointViewSet(viewsets.ReadOnlyModelViewSet):
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EmissionsDataPointDetailSerializer  # Includes audit trail
        return EmissionsDataPointListSerializer  # Lightweight
```

**Example**:
```
GET /api/emissions/
→ EmissionsDataPointListSerializer (100ms, lists 1000 records)
{
    "facility_name": "Plant A",
    "scope_1_emissions": 100.5,
    "year": 2023,
    "validation_error_count": 2,  # Just the count
    "data_quality_score": 85
}

GET /api/emissions/{id}/
→ EmissionsDataPointDetailSerializer (500ms, includes audit trail)
{
    "facility_name": "Plant A",
    ...,
    "validation_errors": [...],  # Full details
    "data_quality_flags": [...],
    "recent_changes": [
        {
            "action": "CREATE",
            "timestamp": "...",
            "user_name": "analyst1@example.com"
        }
    ]
}
```

**Rejected Alternatives**:
- ❌ Single serializer for all actions: Loads too much data for lists
- ❌ Conditional fields in one serializer: Becomes unmaintainable

### 3. DjangoFilterBackend for Filtering (✅ Chosen)

**Decision**: Use `DjangoFilterBackend` + custom `FilterSet` for powerful filtering without custom code.

**Why**:
- **Reusable**: Define filters once in FilterSet class
- **Safe**: Prevents SQL injection (uses Django ORM)
- **Flexible**: Supports complex lookups (gte, lte, range)
- **Standard**: Django convention

**Example**:
```python
# FilterSet class
class EmissionsDataPointFilter(filters.FilterSet):
    year = filters.NumberFilter(field_name='normalized_values__year', lookup_expr='exact')
    quality_score_min = filters.NumberFilter(field_name='data_quality_score', lookup_expr='gte')
    review_status = filters.ChoiceFilter(choices=[...])

# API endpoint
GET /api/emissions/?year=2023&review_status=PENDING&quality_score_min=80
→ Returns filtered queryset
```

**Rejected Alternatives**:
- ❌ Manual query parameter parsing: Verbose, error-prone
- ❌ Hardcoded filters: Can't reuse, hard to extend

### 4. SearchFilter for Text Search (✅ Chosen)

**Decision**: Enable text search on facility_name using `SearchFilter`.

**Why**:
- **Natural**: Analysts search by facility name (intuitive)
- **Fast**: Django ORM generates efficient SQL
- **Flexible**: icontains (case-insensitive substring match)

**Example**:
```python
# ViewSet
search_fields = ['normalized_values__facility_name']

# API
GET /api/emissions/?search=plant
→ Returns all records where facility_name contains "plant"
```

**Rejected Alternatives**:
- ❌ No search: Analysts must scroll through thousands of records
- ❌ PostgreSQL full-text search: Overkill for MVP

### 5. Custom Actions (Detail Routes) (✅ Chosen)

**Decision**: Use @action decorator to add custom endpoints like `/api/emissions/{id}/audit/`.

**Why**:
- **RESTful**: Custom endpoints are named clearly
- **Reusable**: Easy to add more (summary, stats, etc.)
- **Explicit**: Code is clear about what each route does

**Example**:
```python
@action(detail=True, methods=['get'])
def audit(self, request, pk=None):
    """GET /api/emissions/{id}/audit/"""
    emissions = self.get_object()
    audits = AuditLog.objects.filter(object_id=str(emissions.id))
    return Response({'audit_trail': AuditLogSerializer(audits, many=True).data})
```

**Rejected Alternatives**:
- ❌ Separate ViewSet (AuditViewSet): More complex routing
- ❌ Custom URL patterns: Less DRF convention

### 6. ReadOnlyModelViewSet (Not CRUD) (✅ Chosen)

**Decision**: Use `ReadOnlyModelViewSet` (GET only), not full `ModelViewSet` (POST/PUT/DELETE).

**Why**:
- **API tier only reads**: Updates happen via separate endpoints (ingestion, review)
- **Safety**: Can't accidentally delete via API
- **Separation of concerns**: Ingestion has its own endpoints (POST /api/ingest/upload/)

**Why Not Allow Updates**:
- EmissionsDataPoint should be updated via:
  - CSV ingestion pipeline (POST /api/ingest/upload/ → /api/ingest/{id}/normalize/)
  - Analyst review (POST /api/review/{id}/approve/)
  - NOT direct PATCH /api/emissions/{id}/

**Rejected Alternatives**:
- ❌ Full ModelViewSet: Allows direct API modifications (bypasses validation, audit)
- ❌ Custom write views: More code

### 7. Default Ordering (Newest First) (✅ Chosen)

**Decision**: Default ordering is `-created_at` (newest first).

**Why**:
- **User experience**: Analysts see recent uploads first
- **Natural**: Time-series data should show latest
- **Queryable**: Can sort by other fields with query params

**Example**:
```python
ordering = ['-created_at']  # Default
ordering_fields = ['created_at', 'data_quality_score', 'year']

GET /api/emissions/ → newest first
GET /api/emissions/?ordering=data_quality_score → lowest quality first
GET /api/emissions/?ordering=-data_quality_score → highest quality first
```

---

## Implementation Walkthrough

### 1. Serializers (emissions/serializers.py)

**Pattern**:
```python
class EmissionsDataPointListSerializer(serializers.ModelSerializer):
    # Flatten nested JSONB
    facility_name = serializers.CharField(source='normalized_values.facility_name')
    scope_1_emissions = serializers.FloatField(source='normalized_values.scope_1_emissions')
    
    # Include counts (lightweight)
    validation_error_count = serializers.SerializerMethodField()
    
    class Meta:
        model = EmissionsDataPoint
        fields = [...]
```

### 2. Filters (emissions/filters.py)

**Pattern**:
```python
class EmissionsDataPointFilter(filters.FilterSet):
    # Filter by normalized_values.year
    year = filters.NumberFilter(field_name='normalized_values__year')
    
    # Filter by review_status
    review_status = filters.ChoiceFilter(choices=[...])
    
    class Meta:
        model = EmissionsDataPoint
        fields = [...]
```

### 3. ViewSet (emissions/views.py)

**Pattern**:
```python
class EmissionsDataPointViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmissionsDataPoint.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EmissionsDataPointFilter
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EmissionsDataPointDetailSerializer
        return EmissionsDataPointListSerializer
    
    @action(detail=True)
    def audit(self, request, pk=None):
        # Custom action
        ...
```

### 4. URL Routing (emissions/urls.py)

**Pattern**:
```python
router = DefaultRouter()
router.register(r'emissions', EmissionsDataPointViewSet)
urlpatterns = [path('', include(router.urls))]
```

**Generates**:
```
GET    /api/emissions/              → list
GET    /api/emissions/{id}/         → detail
GET    /api/emissions/{id}/audit/   → custom action
GET    /api/emissions/summary/      → list action
```

---

## API Endpoints (Full Reference)

### List with Filtering

```
GET /api/emissions/
?year=2023
&review_status=PENDING
&quality_score_min=80
&facility_name=plant
&ordering=-created_at
```

**Response**:
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
      "year": 2023,
      "review_status": "PENDING",
      "data_quality_score": 85,
      "validation_error_count": 2,
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
    {"field": "methodology", "message": "Missing"}
  ],
  "data_quality_flags": [...],
  "recent_changes": [
    {
      "action": "CREATE",
      "timestamp": "2024-05-27T10:00:00Z",
      "user_name": "analyst1@example.com",
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
      "id": "audit-uuid",
      "action": "CREATE",
      "timestamp": "2024-05-27T10:00:00Z",
      "user_name": "analyst1@example.com",
      "change_summary": {"new_values": {...}}
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

## Interview Questions & Answers

### Q1: Why flatten normalized_values instead of returning it as-is?

**A**: Two reasons:

1. **Frontend simplicity**: React components expect flat props
   ```javascript
   // If nested
   <span>{data.normalized_values.facility_name}</span>  // Deep drilling
   
   // If flattened
   <span>{data.facility_name}</span>  // Direct access
   ```

2. **Type safety**: Serializer declares exact fields
   ```python
   facility_name = serializers.CharField(source='normalized_values.facility_name')
   # Explicitly says: facility_name is a string
   
   # If we return raw JSON
   # {"normalized_values": {...}}  # No type info
   ```

---

### Q2: Why separate list and detail serializers?

**A**: Performance and clarity.

**Without separation** (single serializer):
```
GET /api/emissions/?page=1  (1000 records)
→ Loads full audit trail for each record (1000 queries!)
→ Returns 5MB JSON
→ Takes 30 seconds
```

**With separation**:
```
GET /api/emissions/?page=1  (1000 records)
→ Returns lightweight version (100KB)
→ Takes 200ms

GET /api/emissions/{id}/
→ Returns full audit trail for 1 record
→ Takes 500ms
```

Frontend loads list fast, then detail view is slow only when needed.

---

### Q3: How do we handle missing fields in normalized_values?

**A**: Serializer uses `allow_null=True`:

```python
facility_name = serializers.CharField(
    source='normalized_values.facility_name',
    allow_null=True  # Returns null if missing
)
```

**Result**:
```json
{
  "facility_name": null,
  "scope_1_emissions": 100.5
}
```

Frontend can check `if (data.facility_name) { ... }` safely.

---

### Q4: Can we filter by multiple years (year=2023 OR year=2024)?

**A**: Yes, using comma-separated values with custom filter:

```python
# Current (year=2023 only)
year = filters.NumberFilter(field_name='normalized_values__year')

# For OR logic (year__in):
year = filters.BaseInFilter(
    field_name='normalized_values__year',
    lookup_expr='in'
)

# Usage:
GET /api/emissions/?year=2023,2024,2025
```

Or use multiple requests (simpler for MVP).

---

### Q5: What if PostgreSQL JSONB queries are slow?

**A**: Add database indexes:

```python
# In model Meta
class Meta:
    indexes = [
        models.Index(fields=['normalized_values__year']),
        models.Index(fields=['normalized_values__facility_name']),
    ]
```

Or migrate to separate columns:
```python
class EmissionsDataPoint(models.Model):
    facility_name = CharField()  # Denormalized
    scope_1_emissions = FloatField()
    year = IntegerField()
    # These columns are indexed, searched fast
```

For MVP, JSONB is fine. Optimize later if needed.

---

### Q6: How do we add pagination to list endpoint?

**A**: DRF includes pagination automatically:

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50
}

# API
GET /api/emissions/?page=1
→ Returns records 1-50
→ Includes "count", "next", "previous" links

GET /api/emissions/?page=2
→ Returns records 51-100
```

Frontend loops through pages.

---

### Q7: How do we add custom validation in the serializer?

**A**: Override `validate_` methods:

```python
class EmissionsDataPointSerializer(serializers.ModelSerializer):
    def validate_scope_1_emissions(self, value):
        if value < 0:
            raise serializers.ValidationError("Emissions can't be negative")
        return value
    
    def validate(self, data):
        # Cross-field validation
        if data.get('year') > 2100:
            raise serializers.ValidationError("Year too far in future")
        return data
```

**Result**:
```
POST /api/emissions/ with scope_1_emissions=-50
→ 400 Bad Request: "Emissions can't be negative"
```

---

### Q8: How do we return audit logs with emissions data?

**A**: Use `SerializerMethodField`:

```python
class EmissionsDataPointDetailSerializer(serializers.ModelSerializer):
    recent_changes = serializers.SerializerMethodField()
    
    def get_recent_changes(self, obj):
        audits = AuditLog.objects.filter(
            object_id=str(obj.id)
        ).order_by('-timestamp')[:5]
        return AuditLogSerializer(audits, many=True).data
```

**Result**:
```json
{
  "id": "...",
  "facility_name": "Plant A",
  "recent_changes": [
    {"action": "UPDATE", "timestamp": "...", "user_name": "analyst1@example.com"}
  ]
}
```

---

### Q9: Can we export the filtered results as CSV?

**A**: Add custom action:

```python
@action(detail=False, methods=['get'])
def export_csv(self, request):
    queryset = self.filter_queryset(self.get_queryset())
    
    import csv
    from django.http import HttpResponse
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="emissions.csv"'
    
    writer = csv.DictWriter(response, fieldnames=[...])
    for obj in queryset:
        writer.writerow({...})
    
    return response

# Usage:
GET /api/emissions/export_csv/?year=2023
→ Downloads emissions.csv
```

---

### Q10: How do we prevent analysts from accessing other tenant's data (before Chunk 2.3)?

**A**: For now, add comment noting this is done in Chunk 2.3:

```python
def get_queryset(self):
    queryset = super().get_queryset()
    
    # TODO: After Chunk 2.3 (Multi-Tenancy)
    # if self.request.user.is_authenticated:
    #     queryset = queryset.filter(tenant_id=self.request.user.profile.tenant_id)
    
    return queryset
```

In Chunk 2.3, uncomment this code and test that it works.

---

## Success Criteria

✅ Can list EmissionsDataPoints as JSON
✅ Detail endpoint includes audit trail
✅ Filtering by year, review_status, facility_name works
✅ Search by facility name works
✅ Pagination works (page size configurable)
✅ Serializer handles missing/invalid fields gracefully
✅ API returns 200 for valid requests, 400 for bad filters
✅ Audit endpoint returns change history
✅ Summary endpoint returns statistics
✅ Multiple serializers (list vs. detail) for performance

---

## File Organization

```
breathe/apps/emissions/
├── serializers.py         # EmissionsDataPoint serializers
├── filters.py             # FilterSet for filtering
├── views.py               # ViewSet and custom actions
├── urls.py                # Router and URL registration
└── models.py              # (from Phase 1)

breathe/apps/ingest/
├── serializers_new.py     # RawIngestion, ParsedRecord, NormalizedRecord serializers
└── models.py              # (from Phase 1)
```

---

## Next Steps (After Chunk 2.1)

**Chunk 2.2**: Analyst Review Workflow API
- Endpoints to approve/reject EmissionsDataPoints
- Create ReviewTask model
- POST /api/review/{id}/approve/
- POST /api/review/{id}/reject/

**Chunk 2.3**: Multi-Tenancy Isolation
- Uncomment tenant filtering in get_queryset()
- Implement TenantAwareManager
- Test cross-tenant data isolation

---

**Version**: May 2026
**Status**: Chunk 2.1 architecture ready
**Next**: CHUNK_2_1_INTEGRATION_GUIDE.md with test cases

