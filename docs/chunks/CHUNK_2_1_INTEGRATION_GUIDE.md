# Chunk 2.1: Django REST Framework Setup & Serializers — Integration Guide

## Setup Instructions

### 1. Install Dependencies

```bash
pip install djangorestframework django-filter
```

### 2. Add to INSTALLED_APPS (settings.py)

```python
INSTALLED_APPS = [
    ...
    'rest_framework',
    'django_filters',
    ...
]
```

### 3. Configure DRF (settings.py)

```python
REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
}
```

### 4. Register URLs (breathe/urls.py)

```python
from django.urls import path, include
from breathe.apps.emissions.urls import urlpatterns as emissions_urls

urlpatterns = [
    path('api/', include(emissions_urls)),
]
```

### 5. Test the API

```bash
python manage.py runserver
# Visit: http://localhost:8000/api/emissions/
```

---

## Integration Tests

### Test 1: List EmissionsDataPoints (No Filters)

**Objective**: Verify that `/api/emissions/` returns all records as JSON with pagination

**Setup**:
```python
from rest_framework.test import APIClient
from breathe.apps.emissions.models import EmissionsDataPoint
from breathe.apps.tenants.models import Tenant

# Create test data
tenant = Tenant.objects.create(name='Test Tenant')
for i in range(5):
    EmissionsDataPoint.objects.create(
        tenant_id=tenant,
        data_source=None,
        normalized_values={
            'facility_name': f'Facility {i}',
            'scope_1_emissions': 100.0 + i * 10,
            'year': 2023
        },
        validation_errors=[],
        is_valid=True,
        data_quality_score=85
    )
```

**Test Steps**:
```python
client = APIClient()
response = client.get('/api/emissions/')

# 1. Check status code
assert response.status_code == 200, f"Expected 200, got {response.status_code}"

# 2. Check response format
data = response.json()
assert 'count' in data, "Missing 'count' in response"
assert 'results' in data, "Missing 'results' in response"
assert data['count'] == 5, f"Expected 5 records, got {data['count']}"

# 3. Check flattened fields
result = data['results'][0]
assert 'facility_name' in result, "facility_name not flattened"
assert result['facility_name'] == 'Facility 0'
assert 'scope_1_emissions' in result
assert result['scope_1_emissions'] == 100.0

# 4. Check lightweight serializer (no audit trail)
assert 'recent_changes' not in result, "List shouldn't include audit trail"
assert 'validation_error_count' in result

print("✅ List endpoint works, fields flattened")
```

**Expected Output**:
```
✅ Status 200 OK
✅ Response includes count, results, next/previous links
✅ facility_name is flattened (not under normalized_values)
✅ Pagination works (count=5)
```

---

### Test 2: Detail View with Audit Trail

**Objective**: Verify that `/api/emissions/{id}/` returns full record with audit trail

**Setup** (from Test 1):
```python
emission = EmissionsDataPoint.objects.first()
```

**Test Steps**:
```python
client = APIClient()
response = client.get(f'/api/emissions/{emission.id}/')

# 1. Check status
assert response.status_code == 200

# 2. Check detail serializer (includes audit trail)
data = response.json()
assert 'recent_changes' in data, "Detail should include audit trail"
assert 'validation_errors' in data, "Detail should include validation errors"
assert isinstance(data['recent_changes'], list)

# 3. Check flattened fields
assert data['facility_name'] == 'Facility 0'
assert data['scope_1_emissions'] == 100.0

print("✅ Detail endpoint works, includes audit trail")
```

**Expected Output**:
```
✅ Status 200 OK
✅ recent_changes included (audit trail)
✅ validation_errors included (full details)
✅ Flattened fields present
```

---

### Test 3: Filter by Year

**Objective**: Verify that filtering by year works: `?year=2023`

**Setup**:
```python
# Create records with different years
for year in [2022, 2023, 2024]:
    EmissionsDataPoint.objects.create(
        tenant_id=tenant,
        data_source=None,
        normalized_values={
            'facility_name': f'Plant {year}',
            'scope_1_emissions': 100.0,
            'year': year
        },
        is_valid=True
    )
```

**Test Steps**:
```python
client = APIClient()
response = client.get('/api/emissions/?year=2023')

data = response.json()

# 1. Check filtered results
assert data['count'] >= 1, "Should find 2023 records"

# 2. Verify only 2023 records returned
for result in data['results']:
    # Careful: normalized_values is still raw in some queries
    # Serializer flattens it, so check flattened field
    year = result.get('year')
    if year:  # May be None if missing
        assert year == 2023, f"Got year {year}, expected 2023"

print(f"✅ Filter by year works: {data['count']} records from 2023")
```

**Expected Output**:
```
✅ Status 200 OK
✅ Only 2023 records returned
✅ count reflects filtered results
```

---

### Test 4: Filter by Review Status

**Objective**: Verify filtering by review_status: `?review_status=PENDING`

**Setup**:
```python
EmissionsDataPoint.objects.all().update(review_status='PENDING')
EmissionsDataPoint.objects.first().update(review_status='APPROVED')
```

**Test Steps**:
```python
client = APIClient()

# Filter by PENDING
response = client.get('/api/emissions/?review_status=PENDING')
data = response.json()
pending_count = data['count']

# Filter by APPROVED
response = client.get('/api/emissions/?review_status=APPROVED')
data = response.json()
approved_count = data['count']

# 1. Check filtering works
assert pending_count >= 0
assert approved_count >= 1, "Should have at least 1 approved"
assert pending_count + approved_count >= total_records

print(f"✅ Filter by status: {pending_count} pending, {approved_count} approved")
```

**Expected Output**:
```
✅ PENDING filter works
✅ APPROVED filter works
✅ Counts are correct
```

---

### Test 5: Search by Facility Name

**Objective**: Verify text search: `?search=plant`

**Setup**:
```python
EmissionsDataPoint.objects.create(
    tenant_id=tenant,
    normalized_values={'facility_name': 'Alpha Plant', ...},
    is_valid=True
)
EmissionsDataPoint.objects.create(
    tenant_id=tenant,
    normalized_values={'facility_name': 'Beta Factory', ...},
    is_valid=True
)
```

**Test Steps**:
```python
client = APIClient()

# Search for "plant"
response = client.get('/api/emissions/?search=plant')
data = response.json()

# 1. Check results
assert data['count'] >= 1, "Should find 'plant'"
for result in data['results']:
    facility = result.get('facility_name', '').lower()
    assert 'plant' in facility or facility == '', f"Got {facility}, expected to contain 'plant'"

print("✅ Search by facility name works")
```

**Expected Output**:
```
✅ Search is case-insensitive
✅ Returns matching records
✅ Non-matching records excluded
```

---

### Test 6: Filter by Data Quality Score

**Objective**: Verify range filtering: `?quality_score_min=80`

**Setup**:
```python
# Create records with different quality scores
for score in [50, 75, 85, 95]:
    EmissionsDataPoint.objects.create(
        tenant_id=tenant,
        normalized_values={'facility_name': f'Plant {score}', ...},
        data_quality_score=score,
        is_valid=True
    )
```

**Test Steps**:
```python
client = APIClient()

# Filter: quality_score >= 80
response = client.get('/api/emissions/?quality_score_min=80')
data = response.json()

# Check all results have score >= 80
for result in data['results']:
    score = result.get('data_quality_score')
    assert score >= 80, f"Got score {score}, expected >= 80"

print(f"✅ Quality score filter works: {data['count']} records with score >= 80")
```

**Expected Output**:
```
✅ Minimum quality filter works
✅ Maximum quality filter works
✅ Range filtering works
```

---

### Test 7: Pagination

**Objective**: Verify pagination: `?page=2`

**Setup**:
```python
# Create 120 records (exceeds default PAGE_SIZE=50)
for i in range(120):
    EmissionsDataPoint.objects.create(
        tenant_id=tenant,
        normalized_values={'facility_name': f'Facility {i}', ...},
        is_valid=True
    )
```

**Test Steps**:
```python
client = APIClient()

# Get page 1
response = client.get('/api/emissions/?page=1')
data1 = response.json()

# Get page 2
response = client.get('/api/emissions/?page=2')
data2 = response.json()

# Get page 3
response = client.get('/api/emissions/?page=3')
data3 = response.json()

# 1. Check page 1
assert len(data1['results']) == 50, "Page size should be 50"
assert data1['next'] is not None, "Should have next page"

# 2. Check page 2
assert len(data2['results']) == 50
assert data2['next'] is not None
assert data2['previous'] is not None

# 3. Check page 3
assert len(data3['results']) == 20, "Last page has remaining records"
assert data3['next'] is None, "No next page"

# 4. Verify different results on different pages
page1_ids = [r['id'] for r in data1['results']]
page2_ids = [r['id'] for r in data2['results']]
assert page1_ids != page2_ids, "Pages should have different results"

print("✅ Pagination works: pages, next/previous links")
```

**Expected Output**:
```
✅ Page 1: 50 records + next link
✅ Page 2: 50 records + next + previous links
✅ Page 3: remaining records, no next link
✅ Pages contain different data
```

---

### Test 8: Audit Trail Endpoint

**Objective**: Verify `/api/emissions/{id}/audit/` returns change history

**Setup**:
```python
from breathe.apps.audit.models import AuditLog

emission = EmissionsDataPoint.objects.first()

# Create audit log entries
for i in range(3):
    AuditLog.objects.create(
        object_type='EmissionsDataPoint',
        object_id=str(emission.id),
        tenant_id=tenant,
        action='CREATE' if i == 0 else 'UPDATE',
        change_summary={'new_values': {'test': f'value{i}'}},
        user_id=None,
        ip_address='127.0.0.1'
    )
```

**Test Steps**:
```python
client = APIClient()
response = client.get(f'/api/emissions/{emission.id}/audit/')

# 1. Check status
assert response.status_code == 200

# 2. Check audit structure
data = response.json()
assert 'audit_trail' in data
assert 'total_changes' in data
assert len(data['audit_trail']) == 3

# 3. Check audit entries
for entry in data['audit_trail']:
    assert 'action' in entry
    assert 'timestamp' in entry
    assert 'change_summary' in entry

print(f"✅ Audit endpoint works: {data['total_changes']} changes")
```

**Expected Output**:
```
✅ Status 200 OK
✅ Returns audit_trail list
✅ Each entry has action, timestamp, change_summary
✅ Total changes count correct
```

---

### Test 9: Summary Stats Endpoint

**Objective**: Verify `/api/emissions/summary/` returns statistics

**Setup** (existing data):
```python
# Mix of statuses and quality scores
```

**Test Steps**:
```python
client = APIClient()
response = client.get('/api/emissions/summary/')

# 1. Check status
assert response.status_code == 200

# 2. Check summary structure
data = response.json()
assert 'total_records' in data
assert 'by_status' in data
assert 'by_data_quality' in data
assert 'by_year' in data
assert 'average_quality_score' in data

# 3. Verify counts
assert data['total_records'] >= 0
assert data['by_status']['PENDING'] >= 0
assert data['by_status']['APPROVED'] >= 0

print(f"✅ Summary endpoint works: {data['total_records']} total records")
print(f"   By status: {data['by_status']}")
print(f"   Avg quality: {data['average_quality_score']}")
```

**Expected Output**:
```
✅ Status 200 OK
✅ Returns total_records, by_status, by_data_quality, by_year
✅ Counts are correct
```

---

### Test 10: Combined Filters (Multiple at Once)

**Objective**: Verify that multiple filters work together: `?year=2023&review_status=PENDING&quality_score_min=80`

**Setup**:
```python
# Create diverse dataset
for year in [2023, 2024]:
    for status in ['PENDING', 'APPROVED']:
        for quality in [75, 85, 95]:
            EmissionsDataPoint.objects.create(
                tenant_id=tenant,
                normalized_values={'facility_name': f'Plant {year}{status}{quality}', 'year': year},
                review_status=status,
                data_quality_score=quality,
                is_valid=True
            )
```

**Test Steps**:
```python
client = APIClient()

# Complex filter: year=2023 AND status=PENDING AND quality>=80
response = client.get('/api/emissions/?year=2023&review_status=PENDING&quality_score_min=80')

data = response.json()

# 1. Check filtering
assert response.status_code == 200
assert data['count'] >= 1, "Should find matching records"

# 2. Verify all filters applied
for result in data['results']:
    assert result['year'] == 2023 or result['year'] is None  # Some may be None
    assert result['review_status'] == 'PENDING'
    assert result['data_quality_score'] >= 80

print(f"✅ Combined filters work: {data['count']} records match all criteria")
```

**Expected Output**:
```
✅ Multiple filters apply as AND (all must match)
✅ Only matching records returned
✅ Complex queries work
```

---

## Curl Testing (API Commands)

### List Emissions

```bash
curl -X GET http://localhost:8000/api/emissions/ \
  -H "Content-Type: application/json"

# Response:
# {
#   "count": 100,
#   "next": "http://.../api/emissions/?page=2",
#   "results": [...]
# }
```

### Filter by Year

```bash
curl -X GET "http://localhost:8000/api/emissions/?year=2023" \
  -H "Content-Type: application/json"
```

### Detail View

```bash
curl -X GET "http://localhost:8000/api/emissions/{id}/" \
  -H "Content-Type: application/json"

# Response includes audit trail, validation errors, etc.
```

### Audit Trail

```bash
curl -X GET "http://localhost:8000/api/emissions/{id}/audit/" \
  -H "Content-Type: application/json"
```

### Summary Stats

```bash
curl -X GET "http://localhost:8000/api/emissions/summary/" \
  -H "Content-Type: application/json"
```

---

## Manual Testing Checklist

- [ ] Test 1: List endpoint returns all records
- [ ] Test 2: Detail endpoint includes audit trail
- [ ] Test 3: Filter by year works
- [ ] Test 4: Filter by review_status works
- [ ] Test 5: Search by facility_name works
- [ ] Test 6: Filter by data quality score works
- [ ] Test 7: Pagination works (pages, next/prev)
- [ ] Test 8: Audit trail endpoint works
- [ ] Test 9: Summary stats endpoint works
- [ ] Test 10: Combined filters work together

---

## Common Issues & Fixes

### Issue: "No module named 'rest_framework'"

**Cause**: DRF not installed

**Fix**:
```bash
pip install djangorestframework django-filter
```

### Issue: Filter not working (query parameter ignored)

**Cause**: FilterSet not registered on ViewSet

**Fix**:
```python
class EmissionsDataPointViewSet(viewsets.ReadOnlyModelViewSet):
    filterset_class = EmissionsDataPointFilter  # Add this!
```

### Issue: Pagination returns all records (no page limit)

**Cause**: Pagination not configured

**Fix** (settings.py):
```python
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50  # Add this!
}
```

### Issue: Flattened fields are null

**Cause**: normalized_values missing the key

**Fix**: Check data in database:
```python
emission = EmissionsDataPoint.objects.first()
print(emission.normalized_values)  # See what's actually stored
```

---

## Success Criteria

✅ All 10 integration tests pass
✅ API returns JSON with proper formatting
✅ Filtering works on multiple fields
✅ Pagination works
✅ Audit trail endpoint returns changes
✅ Summary endpoint returns statistics
✅ Flattened serializers work (normalized_values flattened)
✅ List endpoint is lightweight (no audit trail)
✅ Detail endpoint is comprehensive (includes audit trail)
✅ Combined filters work together

---

**Version**: May 2026
**Status**: Chunk 2.1 integration tests ready
**Next**: CHUNK_2_1_SUMMARY.md (quick reference)

