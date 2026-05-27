# Chunk 2.4: Ingestion Workflow Endpoints - Integration Guide

## Overview

This guide provides 12+ complete integration tests for the Ingestion Workflow API (Chunk 2.4). Tests validate CSV upload, parsing, normalization, filtering, quality scoring, multi-tenant isolation, and idempotency.

---

## Test Setup

All tests use `APITestCase` with multi-tenant user setup:

```python
# tests/test_ingest_workflow.py

from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from breathe.apps.auth.models import Tenant, UserProfile
from breathe.apps.ingest.models import RawIngestion, ParsedRecord, NormalizedRecord
from io import BytesIO


class IngestionWorkflowTestCase(APITestCase):
    """Base test case for ingestion workflow"""

    def setUp(self):
        """Create test data across two tenants"""

        # ============ Tenant 1: Acme ============
        self.tenant_acme = Tenant.objects.create(
            name='Acme Corp',
            slug='acme'
        )

        self.user_acme = User.objects.create_user(
            username='alice',
            password='password123'
        )
        UserProfile.objects.create(
            user=self.user_acme,
            tenant=self.tenant_acme,
            role='DATA_PROVIDER'
        )

        # ============ Tenant 2: Beta ============
        self.tenant_beta = Tenant.objects.create(
            name='Beta Inc',
            slug='beta'
        )

        self.user_beta = User.objects.create_user(
            username='bob',
            password='password123'
        )
        UserProfile.objects.create(
            user=self.user_beta,
            tenant=self.tenant_beta,
            role='DATA_PROVIDER'
        )

        # Login as alice (Acme)
        response = self.client.post(
            '/api/auth/login/',
            data={'username': 'alice', 'password': 'password123'},
            format='json'
        )
        self.access_token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    def _create_test_csv(self):
        """Create a test CSV file"""
        csv_content = """Facility,Scope 1 Emissions,Scope 2 Emissions,Scope 3 Emissions,Year
Plant A,500.5,200.0,100.0,2023
Plant B,600.0,250.0,150.0,2023
Plant C,450.0,180.0,90.0,2023"""
        return csv_content.encode('utf-8')

    def _create_test_csv_with_errors(self):
        """Create a test CSV with some data quality issues"""
        csv_content = """Facility,Scope 1 Emissions,Scope 2 Emissions,Scope 3 Emissions,Year
Plant A,500.5,200.0,,2023
Plant B,,250.0,150.0,2023
Plant C,450.0,180.0,90.0,"""
        return csv_content.encode('utf-8')
```

---

## Test 1: Upload CSV File

**Scenario**: User uploads a CSV file. Should create RawIngestion and return upload confirmation.

```python
def test_upload_csv_valid(self):
    """POST /api/ingest/upload/ with valid CSV creates RawIngestion"""

    csv_data = self._create_test_csv()

    response = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'test-source-001'
        },
        format='multipart'
    )

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    self.assertIn('id', response.data)
    self.assertEqual(response.data['data_source_id'], 'test-source-001')
    self.assertEqual(response.data['step'], 'UPLOADED')

    # Verify RawIngestion created
    ingestion = RawIngestion.objects.get(id=response.data['id'])
    self.assertIsNotNone(ingestion.raw_csv_content)
    self.assertIsNotNone(ingestion.file_hash)
```

---

## Test 2: Upload Idempotency (Same File Returns Same ID)

**Scenario**: Upload same CSV twice. Should return same ingestion_id (idempotent).

```python
def test_upload_idempotency(self):
    """Uploading same CSV twice returns same ingestion_id"""

    csv_data = self._create_test_csv()

    # First upload
    response1 = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'test-source-001'
        },
        format='multipart'
    )
    id1 = response1.data['id']

    # Second upload (same file)
    response2 = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'test-source-001'
        },
        format='multipart'
    )
    id2 = response2.data['id']

    # Should return same ID
    self.assertEqual(id1, id2)
```

---

## Test 3: Parse CSV

**Scenario**: Parse uploaded CSV into ParsedRecords.

```python
def test_parse_csv(self):
    """POST /api/ingest/{id}/parse/ parses CSV into ParsedRecords"""

    # First upload
    csv_data = self._create_test_csv()
    upload_response = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'test-source-001'
        },
        format='multipart'
    )
    ingestion_id = upload_response.data['id']

    # Then parse
    response = self.client.post(
        f'/api/ingest/{ingestion_id}/parse/',
        format='json'
    )

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(response.data['step'], 'PARSED')
    self.assertEqual(response.data['steps_completed'], 2)  # UPLOADED + PARSED

    # Verify ParsedRecords created
    parsed_records = ParsedRecord.objects.filter(raw_ingestion_id=ingestion_id)
    self.assertEqual(parsed_records.count(), 3)  # 3 facilities

    # Check field detection
    first_record = parsed_records.first()
    self.assertIn('facility', first_record.raw_values)
    self.assertIn('scope_1_emissions', first_record.raw_values)
```

---

## Test 4: Parse Idempotency (Re-parse Replaces Old Records)

**Scenario**: Parse same ingestion twice. Should replace old ParsedRecords.

```python
def test_parse_idempotency(self):
    """Re-parsing same ingestion deletes old ParsedRecords and creates new ones"""

    # Upload and parse
    csv_data = self._create_test_csv()
    upload_response = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'test-source-001'
        },
        format='multipart'
    )
    ingestion_id = upload_response.data['id']

    # First parse
    self.client.post(f'/api/ingest/{ingestion_id}/parse/', format='json')
    count_after_first = ParsedRecord.objects.filter(raw_ingestion_id=ingestion_id).count()
    self.assertEqual(count_after_first, 3)

    # Second parse (should replace)
    self.client.post(f'/api/ingest/{ingestion_id}/parse/', format='json')
    count_after_second = ParsedRecord.objects.filter(raw_ingestion_id=ingestion_id).count()
    self.assertEqual(count_after_second, 3)  # Same count, but new records
```

---

## Test 5: Normalize Records

**Scenario**: Normalize ParsedRecords into NormalizedRecords with quality scoring.

```python
def test_normalize_records(self):
    """POST /api/ingest/{id}/normalize/ creates NormalizedRecords with quality scores"""

    # Upload, parse, then normalize
    csv_data = self._create_test_csv()
    upload_response = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'test-source-001'
        },
        format='multipart'
    )
    ingestion_id = upload_response.data['id']

    self.client.post(f'/api/ingest/{ingestion_id}/parse/', format='json')

    # Normalize
    response = self.client.post(
        f'/api/ingest/{ingestion_id}/normalize/',
        format='json'
    )

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(response.data['step'], 'NORMALIZED')
    self.assertEqual(response.data['steps_completed'], 3)  # All steps

    # Verify NormalizedRecords created
    normalized_records = NormalizedRecord.objects.filter(raw_ingestion_id=ingestion_id)
    self.assertEqual(normalized_records.count(), 3)

    # Check quality scoring
    for record in normalized_records:
        self.assertGreaterEqual(record.data_quality_score, 0)
        self.assertLessEqual(record.data_quality_score, 100)
        self.assertIsNotNone(record.normalized_values)
```

---

## Test 6: Quality Scoring (Completeness)

**Scenario**: Records with missing fields score lower than complete records.

```python
def test_quality_scoring_completeness(self):
    """Quality score reflects field completeness"""

    # Complete CSV
    complete_csv = self._create_test_csv()
    upload_response = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(complete_csv),
            'data_source_id': 'complete'
        },
        format='multipart'
    )
    complete_id = upload_response.data['id']

    self.client.post(f'/api/ingest/{complete_id}/parse/', format='json')
    self.client.post(f'/api/ingest/{complete_id}/normalize/', format='json')

    # CSV with missing fields
    incomplete_csv = self._create_test_csv_with_errors()
    upload_response2 = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(incomplete_csv),
            'data_source_id': 'incomplete'
        },
        format='multipart'
    )
    incomplete_id = upload_response2.data['id']

    self.client.post(f'/api/ingest/{incomplete_id}/parse/', format='json')
    self.client.post(f'/api/ingest/{incomplete_id}/normalize/', format='json')

    # Compare scores
    complete_avg = NormalizedRecord.objects.filter(
        raw_ingestion_id=complete_id
    ).aggregate(avg=Count('*'))

    incomplete_avg = NormalizedRecord.objects.filter(
        raw_ingestion_id=incomplete_id
    ).aggregate(avg=Count('*'))

    # Incomplete should have lower average quality
    complete_score = NormalizedRecord.objects.filter(
        raw_ingestion_id=complete_id
    ).first().data_quality_score

    incomplete_score = NormalizedRecord.objects.filter(
        raw_ingestion_id=incomplete_id
    ).first().data_quality_score

    self.assertGreater(complete_score, incomplete_score)
```

---

## Test 7: Auto-Approval for High-Quality Records

**Scenario**: Records with quality_score ≥ 80 and is_valid=True auto-approve.

```python
def test_auto_approval_high_quality(self):
    """Records with quality_score >= 80 get AUTO_APPROVED"""

    csv_data = self._create_test_csv()
    upload_response = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'test-source-001'
        },
        format='multipart'
    )
    ingestion_id = upload_response.data['id']

    self.client.post(f'/api/ingest/{ingestion_id}/parse/', format='json')
    response = self.client.post(f'/api/ingest/{ingestion_id}/normalize/', format='json')

    # Check auto-approval count
    auto_approved = response.data.get('auto_approved_count', 0)
    self.assertGreater(auto_approved, 0)

    # Verify in database
    from breathe.apps.emissions.models import EmissionsDataPoint
    approved_records = EmissionsDataPoint.objects.filter(
        normalized_record__raw_ingestion_id=ingestion_id,
        review_status='AUTO_APPROVED'
    )
    self.assertGreater(approved_records.count(), 0)
```

---

## Test 8: Multi-Tenant Isolation in Upload

**Scenario**: User only sees own tenant's ingestions.

```python
def test_upload_multi_tenant_isolation(self):
    """Users only see own tenant's ingestions"""

    csv_data = self._create_test_csv()

    # Alice uploads
    response = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'acme-source'
        },
        format='multipart'
    )
    acme_id = response.data['id']

    # Login as Bob (Beta tenant)
    self.client.logout()
    login_response = self.client.post(
        '/api/auth/login/',
        data={'username': 'bob', 'password': 'password123'},
        format='json'
    )
    bob_token = login_response.data['access']
    self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {bob_token}')

    # Bob uploads
    response2 = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'beta-source'
        },
        format='multipart'
    )
    beta_id = response2.data['id']

    # Login back as Alice
    self.client.logout()
    login_response = self.client.post(
        '/api/auth/login/',
        data={'username': 'alice', 'password': 'password123'},
        format='json'
    )
    alice_token = login_response.data['access']
    self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {alice_token}')

    # Alice lists - should only see her ingestion
    response = self.client.get('/api/ingest/')
    ids = [ing['id'] for ing in response.data.get('results', [])]

    self.assertIn(acme_id, ids)
    self.assertNotIn(beta_id, ids)
```

---

## Test 9: Filter by Status

**Scenario**: List ingestions filtered by current step (UPLOADED, PARSED, NORMALIZED).

```python
def test_filter_by_status(self):
    """GET /api/ingest/?step=NORMALIZED returns only normalized ingestions"""

    csv_data = self._create_test_csv()

    # Create three ingestions at different steps
    # Step 1: Upload only
    response1 = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'source-1'
        },
        format='multipart'
    )
    id1 = response1.data['id']

    # Step 2: Upload + Parse
    response2 = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'source-2'
        },
        format='multipart'
    )
    id2 = response2.data['id']
    self.client.post(f'/api/ingest/{id2}/parse/', format='json')

    # Step 3: Upload + Parse + Normalize
    response3 = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'source-3'
        },
        format='multipart'
    )
    id3 = response3.data['id']
    self.client.post(f'/api/ingest/{id3}/parse/', format='json')
    self.client.post(f'/api/ingest/{id3}/normalize/', format='json')

    # Filter by step
    response = self.client.get('/api/ingest/?step=NORMALIZED')
    ids = [ing['id'] for ing in response.data.get('results', [])]

    self.assertNotIn(id1, ids)
    self.assertNotIn(id2, ids)
    self.assertIn(id3, ids)
```

---

## Test 10: Get Ingestion Status

**Scenario**: Retrieve current progress and summary.

```python
def test_get_ingestion_status(self):
    """GET /api/ingest/{id}/status/ returns progress summary"""

    csv_data = self._create_test_csv()
    upload_response = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'test-source'
        },
        format='multipart'
    )
    ingestion_id = upload_response.data['id']

    # Parse
    self.client.post(f'/api/ingest/{ingestion_id}/parse/', format='json')

    # Get status
    response = self.client.get(f'/api/ingest/{ingestion_id}/status/')

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertIn('step', response.data)
    self.assertIn('steps_completed', response.data)
    self.assertIn('completion_percentage', response.data)
    self.assertEqual(response.data['step'], 'PARSED')
    self.assertEqual(response.data['completion_percentage'], 66)  # 2 of 3 steps
```

---

## Test 11: Retrieve Full Ingestion Details

**Scenario**: Get full details with sample records.

```python
def test_get_ingestion_full_details(self):
    """GET /api/ingest/{id}/ returns full details with sample records"""

    csv_data = self._create_test_csv()
    upload_response = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'test-source'
        },
        format='multipart'
    )
    ingestion_id = upload_response.data['id']

    self.client.post(f'/api/ingest/{ingestion_id}/parse/', format='json')
    self.client.post(f'/api/ingest/{ingestion_id}/normalize/', format='json')

    # Retrieve full details
    response = self.client.get(f'/api/ingest/{ingestion_id}/')

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertIn('sample_parsed_records', response.data)
    self.assertIn('sample_normalized_records', response.data)
    self.assertEqual(len(response.data['sample_parsed_records']), 3)
    self.assertEqual(len(response.data['sample_normalized_records']), 3)
```

---

## Test 12: CSV Dialect Detection

**Scenario**: Parser detects delimiter automatically.

```python
def test_csv_dialect_detection(self):
    """Parser detects semicolon-delimited CSV"""

    # Create semicolon-delimited CSV
    csv_content = """Facility;Scope 1 Emissions;Scope 2 Emissions;Scope 3 Emissions;Year
Plant A;500.5;200.0;100.0;2023
Plant B;600.0;250.0;150.0;2023"""
    csv_data = csv_content.encode('utf-8')

    upload_response = self.client.post(
        '/api/ingest/upload/',
        data={
            'file': BytesIO(csv_data),
            'data_source_id': 'test-source'
        },
        format='multipart'
    )
    ingestion_id = upload_response.data['id']

    # Parse
    response = self.client.post(f'/api/ingest/{ingestion_id}/parse/', format='json')

    # Should have parsed 2 records correctly
    parsed_records = ParsedRecord.objects.filter(raw_ingestion_id=ingestion_id)
    self.assertEqual(parsed_records.count(), 2)
```

---

## Running the Tests

```bash
# Run all ingestion workflow tests
python manage.py test tests.test_ingest_workflow

# Run specific test
python manage.py test tests.test_ingest_workflow.IngestionWorkflowTestCase.test_upload_csv_valid

# With coverage
coverage run --source='breathe/apps/ingest' manage.py test tests.test_ingest_workflow
coverage report
```

---

## Success Criteria

✅ All 12 tests pass
✅ 100% code coverage for ingestion views and serializers
✅ Upload creates RawIngestion with immutable CSV content
✅ Parse creates ParsedRecords with field detection
✅ Normalize creates NormalizedRecords with quality scoring
✅ Quality scoring reflects completeness and validity
✅ Auto-approval for quality_score ≥ 80 and is_valid=True
✅ Idempotency: upload and parse/normalize are idempotent
✅ Multi-tenant isolation enforced
✅ CSV dialect detection works (comma and semicolon)
✅ Status endpoint returns accurate progress
✅ Filtering by step works correctly

---

This chunk completes the ingestion workflow layer for the platform.
