# Chunk 2.5: Data Export & Reporting - Integration Guide

## Overview

This guide provides 12+ complete integration tests for the Data Export & Reporting API (Chunk 2.5). Tests validate CSV/JSON export, filtering, summary statistics, and multi-tenant isolation.

---

## Test Setup

All tests use `APITestCase` with multi-tenant emissions data:

```python
# tests/test_export_reporting.py

from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from breathe.apps.auth.models import Tenant, UserProfile
from breathe.apps.emissions.models import EmissionsDataPoint, NormalizedRecord
from breathe.apps.ingest.models import RawIngestion
import csv
from io import StringIO


class ExportReportingTestCase(APITestCase):
    """Base test case for export and reporting"""

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
            role='ANALYST'
        )

        # Create emissions records for Acme (2023)
        for i in range(10):
            self._create_emissions_record(
                tenant=self.tenant_acme,
                facility=f'Plant {chr(65+i)}',  # Plant A, B, C, ...
                scope_1=500 + i * 100,
                year=2023,
                quality_score=80 + i,  # 80-89
                status='APPROVED'
            )

        # Create emissions records for Acme (2022)
        for i in range(5):
            self._create_emissions_record(
                tenant=self.tenant_acme,
                facility=f'Plant {chr(65+i)}',
                scope_1=400 + i * 100,
                year=2022,
                quality_score=75,
                status='APPROVED'
            )

        # Create pending record for Acme
        self._create_emissions_record(
            tenant=self.tenant_acme,
            facility='Plant Z',
            scope_1=1000,
            year=2023,
            quality_score=50,
            status='PENDING'
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
            role='ANALYST'
        )

        # Create emissions records for Beta
        for i in range(5):
            self._create_emissions_record(
                tenant=self.tenant_beta,
                facility=f'Beta Plant {i}',
                scope_1=600 + i * 100,
                year=2023,
                quality_score=85,
                status='APPROVED'
            )

        # Login as alice (Acme)
        response = self.client.post(
            '/api/auth/login/',
            data={'username': 'alice', 'password': 'password123'},
            format='json'
        )
        self.access_token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

    def _create_emissions_record(self, tenant, facility, scope_1, year, quality_score, status):
        """Helper to create emissions record"""
        # Create normalized record
        normalized = NormalizedRecord.objects.create(
            tenant_id=tenant.id,
            facility_name=facility,
            scope_1_emissions=scope_1,
            scope_2_emissions=200,
            scope_3_emissions=100,
            reporting_year=year,
            is_valid=(status == 'APPROVED'),
            data_quality_score=quality_score,
            normalized_values={
                'facility_name': facility,
                'scope_1_emissions': scope_1,
                'scope_2_emissions': 200,
                'scope_3_emissions': 100,
                'reporting_year': year
            }
        )

        # Create emissions data point
        EmissionsDataPoint.objects.create(
            tenant_id=tenant.id,
            normalized_record=normalized,
            review_status=status,
            data_quality_score=quality_score,
            normalized_values=normalized.normalized_values
        )
```

---

## Test 1: Export CSV Default (Approved Records)

**Scenario**: User downloads CSV. Should get approved records only.

```python
def test_export_csv_default_approved(self):
    """GET /api/emissions/export/?format=csv returns approved records"""

    response = self.client.get('/api/emissions/export/?format=csv')

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(response['Content-Type'], 'text/csv')

    # Parse CSV
    csv_reader = csv.DictReader(
        StringIO(response.content.decode('utf-8'))
    )
    rows = list(csv_reader)

    # Should have 15 approved records (10 from 2023 + 5 from 2022)
    self.assertEqual(len(rows), 15)

    # Should NOT have pending record
    facilities = [row['Facility'] for row in rows]
    self.assertNotIn('Plant Z', facilities)

    # Check columns
    expected_cols = [
        'Facility',
        'Scope 1 Emissions (tCO2e)',
        'Year',
        'Status'
    ]
    for col in expected_cols:
        self.assertIn(col, csv_reader.fieldnames)
```

---

## Test 2: Export JSON Default (Approved Records)

**Scenario**: User requests JSON. Should get records + metadata.

```python
def test_export_json_default_approved(self):
    """GET /api/emissions/export/?format=json returns approved records with metadata"""

    response = self.client.get('/api/emissions/export/?format=json')

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    self.assertEqual(set(response.data.keys()), {'metadata', 'records'})

    # Check metadata
    metadata = response.data['metadata']
    self.assertEqual(metadata['tenant_name'], 'Acme Corp')
    self.assertEqual(metadata['record_count'], 15)
    self.assertEqual(metadata['generated_by'], 'alice')
    self.assertIn('export_timestamp', metadata)

    # Check records
    records = response.data['records']
    self.assertEqual(len(records), 15)

    # Should not include pending
    statuses = [r['review_status'] for r in records]
    self.assertFalse(any(s == 'PENDING' for s in statuses))
```

---

## Test 3: Filter by Year

**Scenario**: Export only 2023 records using year filter.

```python
def test_export_filter_by_year(self):
    """GET /api/emissions/export/?year=2023 returns only 2023 records"""

    response = self.client.get('/api/emissions/export/?format=json&year=2023')

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)

    records = response.data['records']
    self.assertEqual(len(records), 11)  # 10 approved + 1 pending

    # All should be 2023
    years = [r['reporting_year'] for r in records]
    self.assertTrue(all(y == 2023 for y in years))
```

---

## Test 4: Filter by Status

**Scenario**: User wants pending records specifically.

```python
def test_export_filter_by_status(self):
    """GET /api/emissions/export/?status=PENDING returns pending records"""

    response = self.client.get('/api/emissions/export/?format=json&status=PENDING')

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)

    records = response.data['records']
    self.assertEqual(len(records), 1)  # Only Plant Z
    self.assertEqual(records[0]['facility_name'], 'Plant Z')
    self.assertEqual(records[0]['review_status'], 'PENDING')
```

---

## Test 5: Combined Filters (Year + Status)

**Scenario**: Export 2023 approved records only.

```python
def test_export_combined_filters(self):
    """GET /api/emissions/export/?year=2023&status=APPROVED returns filtered records"""

    response = self.client.get(
        '/api/emissions/export/?format=json&year=2023&status=APPROVED'
    )

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)

    records = response.data['records']
    self.assertEqual(len(records), 10)  # Only 2023 approved

    # All should be 2023 and approved
    for record in records:
        self.assertEqual(record['reporting_year'], 2023)
        self.assertEqual(record['review_status'], 'APPROVED')
```

---

## Test 6: CSV Format Validity

**Scenario**: CSV should be properly formatted and parseable.

```python
def test_csv_format_valid(self):
    """CSV is valid, properly formatted, all fields present"""

    response = self.client.get('/api/emissions/export/?format=csv')

    # Parse and validate
    csv_reader = csv.DictReader(
        StringIO(response.content.decode('utf-8'))
    )

    for row in csv_reader:
        # All fields should be present
        self.assertIsNotNone(row['Facility'])
        self.assertIsNotNone(row['Scope 1 Emissions (tCO2e)'])
        self.assertIsNotNone(row['Year'])
        self.assertIsNotNone(row['Status'])

        # Numeric fields should be convertible
        if row['Scope 1 Emissions (tCO2e)']:
            try:
                float(row['Scope 1 Emissions (tCO2e)'])
            except ValueError:
                self.fail(f"Invalid number: {row['Scope 1 Emissions (tCO2e)']}")
```

---

## Test 7: Summary Endpoint Returns All Metrics

**Scenario**: Dashboard requests summary. Should get counts and totals.

```python
def test_summary_returns_all_metrics(self):
    """GET /api/emissions/summary/ returns complete metrics"""

    response = self.client.get('/api/emissions/summary/')

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_200_OK)

    summary = response.data

    # Basic counts
    self.assertGreaterEqual(summary['total_records'], 15)
    self.assertGreaterEqual(summary['approved_records'], 15)

    # By status
    self.assertIn('by_status', summary)
    self.assertIn('by_year', summary)
    self.assertIn('by_facility', summary)
    self.assertIn('by_quality_tier', summary)

    # Aggregates
    self.assertGreater(summary['total_scope_1'], 0)
    self.assertGreater(summary['total_scope_2'], 0)
    self.assertGreater(summary['total_emissions'], 0)
```

---

## Test 8: Quality Tiers in Summary

**Scenario**: Summary breaks down records by quality score tiers.

```python
def test_summary_quality_tiers(self):
    """Summary includes by_quality_tier with 4 tiers"""

    response = self.client.get('/api/emissions/summary/')

    tiers = response.data['by_quality_tier']

    # Should have all tiers
    self.assertIn('0-40', tiers)
    self.assertIn('40-70', tiers)
    self.assertIn('70-80', tiers)
    self.assertIn('80-100', tiers)

    # Records with score 80+ should be in 80-100 tier
    high_quality = tiers['80-100']
    self.assertGreater(high_quality, 0)
```

---

## Test 9: Multi-Tenant Isolation in Export

**Scenario**: Alice (Acme) exports. Should NOT see Bob's (Beta) data.

```python
def test_export_multi_tenant_isolation(self):
    """Users only see own tenant's data in export"""

    response = self.client.get('/api/emissions/export/?format=json')

    records = response.data['records']

    # Should have Acme's data (15 approved)
    self.assertEqual(len(records), 15)

    # Should NOT have Beta's data
    facilities = [r['facility_name'] for r in records]
    self.assertFalse(any('Beta' in f for f in facilities))

    # Metadata should show Acme
    self.assertEqual(response.data['metadata']['tenant_name'], 'Acme Corp')
```

---

## Test 10: Empty Export Returns Error

**Scenario**: No records match filters → appropriate error.

```python
def test_export_no_records_error(self):
    """GET /api/emissions/export/?year=1900 with no matches returns error"""

    response = self.client.get('/api/emissions/export/?year=1900&format=csv')

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    self.assertIn('detail', response.data)
```

---

## Test 11: Summary Multi-Tenant Isolation

**Scenario**: Summary only shows user's tenant data.

```python
def test_summary_multi_tenant_isolation(self):
    """GET /api/emissions/summary/ only counts own tenant's records"""

    response = self.client.get('/api/emissions/summary/')

    summary = response.data

    # Alice (Acme) has 16 total records (15 approved + 1 pending)
    self.assertEqual(summary['total_records'], 16)

    # Should NOT count Beta's 5 records
    self.assertNotEqual(summary['total_records'], 21)
```

---

## Test 12: Invalid Format Parameter

**Scenario**: Unsupported format should error.

```python
def test_export_invalid_format(self):
    """GET /api/emissions/export/?format=invalid returns error"""

    response = self.client.get('/api/emissions/export/?format=xml')

    # Assertions
    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    self.assertIn('format must be', str(response.data))
```

---

## Running the Tests

```bash
# Run all export/reporting tests
python manage.py test tests.test_export_reporting

# Run specific test
python manage.py test tests.test_export_reporting.ExportReportingTestCase.test_export_csv_default_approved

# With coverage
coverage run --source='breathe/apps/emissions' manage.py test tests.test_export_reporting
coverage report
```

---

## Success Criteria

✅ All 12 tests pass
✅ 100% code coverage for export/reporting views and serializers
✅ CSV properly formatted with headers and data rows
✅ JSON includes metadata object with audit context
✅ Default filter (approved only) works
✅ Year and status filters work independently and together
✅ Summary endpoint returns complete metrics
✅ Quality tiers breakdown records correctly
✅ Multi-tenant isolation enforced
✅ Error handling for invalid parameters

---

This chunk completes the basic export and reporting layer for the platform.
