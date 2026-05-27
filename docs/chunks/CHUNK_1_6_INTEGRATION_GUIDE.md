# Chunk 1.6: Audit Logging (Every Change) — Integration Guide

## Setup Instructions

### 1. Add to INSTALLED_APPS (settings.py)

```python
INSTALLED_APPS = [
    ...
    'breathe.apps.audit',
    ...
]
```

### 2. Apply Migrations

```bash
python manage.py makemigrations audit
python manage.py migrate audit
```

This creates:
- `audit_audit_log` table
- Indexes on tenant_id, object_type, object_id, action, timestamp, user_id

### 3. Register Signal Handlers

The signals are registered automatically when the app loads (apps.py ready() method).

Verify in shell:
```python
from django.core.signals import post_save
from breathe.apps.audit.signals import log_emissions_data_point_change
# If no errors, signals are registered

# Check thread-local context
from breathe.apps.audit.signals import set_audit_context, get_audit_context
set_audit_context(user=user_obj, tenant_id=tenant_obj)
ctx = get_audit_context()
print(ctx)  # Should show user and tenant
```

---

## Integration Tests

### Test 1: Create EmissionsDataPoint → AuditLog Created

**Objective**: Verify that creating an EmissionsDataPoint automatically creates an AuditLog with action='CREATE'

**Setup**:
```python
from django.contrib.auth.models import User
from breathe.apps.tenants.models import Tenant
from breathe.apps.emissions.models import EmissionsDataPoint
from breathe.apps.audit.models import AuditLog
from breathe.apps.audit.signals import set_audit_context

# Create test data
tenant = Tenant.objects.create(name='Test Corp')
user = User.objects.create_user(username='analyst1', email='a1@test.com')
```

**Test Steps**:
```python
# 1. Set audit context (simulate middleware)
set_audit_context(user=user, tenant_id=tenant, ip_address='192.168.1.100')

# 2. Create EmissionsDataPoint
emissions = EmissionsDataPoint.objects.create(
    tenant_id=tenant,
    facility_name='Facility X',
    scope_1_emissions=100.5,
    scope_2_emissions=50.0,
    reporting_year=2023,
    data_source='CSV Upload',
    is_verified=True
)

# 3. Verify AuditLog was created
audit = AuditLog.objects.filter(
    object_type='EmissionsDataPoint',
    object_id=str(emissions.id)
).first()

assert audit is not None, "AuditLog not created"
assert audit.action == 'CREATE', f"Expected CREATE, got {audit.action}"
assert audit.user_id == user, "User not captured"
assert audit.ip_address == '192.168.1.100', "IP not captured"
assert audit.tenant_id == tenant, "Tenant not captured"
assert 'new_values' in audit.change_summary, "new_values not in change_summary"
assert audit.change_summary['new_values']['facility_name'] == 'Facility X'
```

**Expected Output**:
```
✅ AuditLog created with action='CREATE'
✅ User, IP, tenant captured correctly
✅ change_summary contains new_values with all fields
```

---

### Test 2: Update EmissionsDataPoint → AuditLog Shows old vs. new

**Objective**: Verify that updating a record creates an AuditLog with action='UPDATE' showing old vs. new values

**Setup** (from Test 1):
```python
# emissions object already created
emissions = EmissionsDataPoint.objects.get(facility_name='Facility X')
```

**Test Steps**:
```python
# 1. Set audit context
set_audit_context(user=user, tenant_id=tenant, ip_address='192.168.1.101')

# 2. Update the record
emissions.facility_name = 'Facility X (corrected)'
emissions.scope_1_emissions = 105.2
emissions.save()

# 3. Query new AuditLog entry
audit = AuditLog.objects.filter(
    object_type='EmissionsDataPoint',
    object_id=str(emissions.id),
    action='UPDATE'
).order_by('-timestamp').first()

assert audit is not None, "UPDATE AuditLog not created"
assert audit.action == 'UPDATE'

# 4. Verify old_values and new_values
changes = audit.change_summary
assert 'old_values' in changes
assert 'new_values' in changes

old = changes['old_values']
new = changes['new_values']

assert old['facility_name'] == 'Facility X'
assert new['facility_name'] == 'Facility X (corrected)'
assert old['scope_1_emissions'] == '100.5'
assert new['scope_1_emissions'] == '105.2'

print("Old facility_name:", old['facility_name'])
print("New facility_name:", new['facility_name'])
```

**Expected Output**:
```
✅ AuditLog created with action='UPDATE'
✅ old_values shows previous data
✅ new_values shows updated data
✅ Unchanged fields also captured (for full history)
```

---

### Test 3: Delete EmissionsDataPoint → AuditLog Created

**Objective**: Verify that deleting a record creates an AuditLog with action='DELETE'

**Setup**:
```python
# Create and delete a record
emissions = EmissionsDataPoint.objects.create(
    tenant_id=tenant,
    facility_name='Facility to Delete',
    scope_1_emissions=50.0,
    reporting_year=2023,
)
emissions_id = emissions.id
```

**Test Steps**:
```python
# 1. Set audit context
set_audit_context(user=user, tenant_id=tenant)

# 2. Delete the record
emissions.delete()

# 3. Verify AuditLog was created (can still query after delete)
audit = AuditLog.objects.filter(
    object_type='EmissionsDataPoint',
    object_id=str(emissions_id),
    action='DELETE'
).first()

assert audit is not None, "DELETE AuditLog not created"
assert audit.action == 'DELETE'
assert 'old_values' in audit.change_summary
assert audit.change_summary['old_values']['facility_name'] == 'Facility to Delete'
assert 'new_values' not in audit.change_summary, "DELETE should not have new_values"

print("✅ Deleted record audited successfully")
```

**Expected Output**:
```
✅ AuditLog created with action='DELETE'
✅ old_values contains the deleted record's data
✅ new_values is absent (no new state after deletion)
```

---

### Test 4: Query Audit Trail for Specific Record

**Objective**: Verify that analysts can query the full audit trail (CREATE → UPDATE → UPDATE) for a record

**Setup**:
```python
set_audit_context(user=user, tenant_id=tenant)

# Create a record
emissions = EmissionsDataPoint.objects.create(
    tenant_id=tenant,
    facility_name='Facility Y',
    scope_1_emissions=100.0,
    reporting_year=2023
)
emissions_id = emissions.id
```

**Test Steps**:
```python
# 1. Update the record multiple times
emissions.scope_1_emissions = 105.0
emissions.save()

emissions.scope_1_emissions = 110.0
emissions.save()

# 2. Query full audit trail
audit_trail = AuditLog.objects.filter(
    object_type='EmissionsDataPoint',
    object_id=str(emissions_id)
).order_by('timestamp')

assert audit_trail.count() == 3, f"Expected 3 audit entries, got {audit_trail.count()}"

# 3. Verify chronological order
assert audit_trail[0].action == 'CREATE'
assert audit_trail[1].action == 'UPDATE'
assert audit_trail[1].change_summary['old_values']['scope_1_emissions'] == '100.0'
assert audit_trail[1].change_summary['new_values']['scope_1_emissions'] == '105.0'

assert audit_trail[2].action == 'UPDATE'
assert audit_trail[2].change_summary['old_values']['scope_1_emissions'] == '105.0'
assert audit_trail[2].change_summary['new_values']['scope_1_emissions'] == '110.0'

print("✅ Full audit trail retrieved successfully")
print(f"   CREATE → UPDATE (100 → 105) → UPDATE (105 → 110)")
```

**Expected Output**:
```
✅ 3 AuditLog entries found in chronological order
✅ Each UPDATE shows the transition
✅ Full lineage visible: 100.0 → 105.0 → 110.0
```

---

### Test 5: Tenant Isolation in Audit Logs

**Objective**: Verify that analysts from Tenant A can't see audit logs from Tenant B

**Setup**:
```python
tenant_a = Tenant.objects.create(name='Tenant A')
tenant_b = Tenant.objects.create(name='Tenant B')

user_a = User.objects.create_user(username='analyst_a')
user_b = User.objects.create_user(username='analyst_b')
```

**Test Steps**:
```python
# 1. Analyst A creates a record
set_audit_context(user=user_a, tenant_id=tenant_a)
emissions_a = EmissionsDataPoint.objects.create(
    tenant_id=tenant_a,
    facility_name='Facility A',
    scope_1_emissions=100.0,
    reporting_year=2023
)

# 2. Analyst B creates a record
set_audit_context(user=user_b, tenant_id=tenant_b)
emissions_b = EmissionsDataPoint.objects.create(
    tenant_id=tenant_b,
    facility_name='Facility B',
    scope_1_emissions=200.0,
    reporting_year=2023
)

# 3. Verify tenant isolation
audits_a = AuditLog.objects.filter(tenant_id=tenant_a)
audits_b = AuditLog.objects.filter(tenant_id=tenant_b)

assert audits_a.count() >= 1, "Tenant A should have at least 1 audit log"
assert audits_b.count() >= 1, "Tenant B should have at least 1 audit log"

# 4. Verify Tenant A can't see Tenant B's logs
for audit in audits_a:
    assert audit.object_id != str(emissions_b.id), "Tenant isolation violated!"

print("✅ Tenant isolation enforced")
print(f"   Tenant A: {audits_a.count()} logs")
print(f"   Tenant B: {audits_b.count()} logs")
```

**Expected Output**:
```
✅ Each tenant's audit logs are isolated
✅ Analysts from Tenant A see only Tenant A's logs
✅ Analysts from Tenant B see only Tenant B's logs
```

---

### Test 6: Attempt to Update AuditLog → Error

**Objective**: Verify that trying to update an AuditLog raises ValueError (immutability)

**Setup**:
```python
audit_log = AuditLog.objects.first()
assert audit_log is not None
```

**Test Steps**:
```python
# 1. Try to modify an audit log
try:
    audit_log.ip_address = '999.999.999.999'  # Change it
    audit_log.save()  # This should fail
    
    assert False, "Should have raised ValueError"
except ValueError as e:
    assert "immutable" in str(e).lower(), f"Wrong error message: {e}"
    print(f"✅ Correctly blocked update with error: {e}")

# 2. Verify the record wasn't actually modified
audit_log.refresh_from_db()
assert audit_log.ip_address != '999.999.999.999', "Record was modified!"
```

**Expected Output**:
```
✅ ValueError raised: "AuditLog entries are immutable and cannot be modified"
✅ Record remains unchanged in database
```

---

### Test 7: Attempt to Delete AuditLog → Error

**Objective**: Verify that trying to delete an AuditLog raises ValueError

**Setup**:
```python
audit_log = AuditLog.objects.first()
```

**Test Steps**:
```python
# 1. Try to delete the audit log
try:
    audit_log.delete()
    assert False, "Should have raised ValueError"
except ValueError as e:
    assert "immutable" in str(e).lower()
    print(f"✅ Delete blocked: {e}")

# 2. Verify it still exists
assert AuditLog.objects.filter(id=audit_log.id).exists(), "Record was deleted!"
print("✅ Record still exists in database")
```

**Expected Output**:
```
✅ ValueError raised: "AuditLog entries are immutable and cannot be deleted"
✅ Record still exists in database (can't delete)
```

---

### Test 8: Batch Operations Tracked Individually

**Objective**: Verify that when creating multiple records, each gets its own AuditLog

**Setup**:
```python
count_before = AuditLog.objects.count()
```

**Test Steps**:
```python
# 1. Create multiple records in loop (not bulk_create)
set_audit_context(user=user, tenant_id=tenant)
records = []
for i in range(3):
    record = EmissionsDataPoint.objects.create(
        tenant_id=tenant,
        facility_name=f'Facility Batch {i}',
        scope_1_emissions=100.0 + i,
        reporting_year=2023
    )
    records.append(record)

# 2. Verify each got an AuditLog
count_after = AuditLog.objects.count()
new_audits = count_after - count_before

assert new_audits == 3, f"Expected 3 audits, got {new_audits}"
print(f"✅ Created {new_audits} AuditLog entries for {len(records)} records")

# 3. Verify each audit has correct data
for i, record in enumerate(records):
    audit = AuditLog.objects.filter(
        object_id=str(record.id),
        action='CREATE'
    ).first()
    assert audit is not None
    assert audit.change_summary['new_values']['facility_name'] == f'Facility Batch {i}'
```

**Expected Output**:
```
✅ 3 AuditLog entries created (one per record)
✅ Each audit log correctly captures the record's data
```

---

### Test 9: Django Admin Shows All Audit Entries (Read-Only)

**Objective**: Verify that Django admin displays audit logs in read-only mode

**Setup**:
```bash
# In Django admin
# Visit http://localhost:8000/admin/audit/auditlog/
```

**Manual Test Steps**:

1. **Login to admin** with superuser account
2. **Navigate to**: Audit > Audit Logs
3. **Verify display**:
   - ✅ List shows all AuditLog entries
   - ✅ Columns: When, Action (badge), Object Type, Object ID, User, Tenant
   - ✅ Filters work: action, object_type, tenant_id, timestamp
   - ✅ Search works: search by object_id, username
4. **Click on an audit entry**:
   - ✅ Detail view shows all fields
   - ✅ change_summary is formatted as pretty JSON
   - ✅ No "Save" button (read-only)
   - ✅ No "Delete" button
5. **Try to edit**: 
   - ✅ Can't modify fields (all readonly)
6. **Try to delete**:
   - ✅ No delete action available

**Verification Code** (if testing programmatically):
```python
from django.contrib.admin.sites import AdminSite
from breathe.apps.audit.admin import AuditLogAdmin
from breathe.apps.audit.models import AuditLog

admin = AuditLogAdmin(AuditLog, AdminSite())

# Check permissions
user = User.objects.create_superuser('admin', 'a@test.com', 'pass')
assert admin.has_add_permission(None) == False
assert admin.has_change_permission(None) == False
assert admin.has_delete_permission(None) == False

print("✅ AuditLogAdmin is read-only")
```

**Expected Output**:
```
✅ Django admin shows audit logs in read-only mode
✅ No add/edit/delete permissions
✅ Filters and search work correctly
✅ change_summary displayed as formatted JSON
```

---

### Test 10: change_summary JSON is Queryable

**Objective**: Verify that we can query audit logs by change_summary JSON values

**Setup**:
```python
set_audit_context(user=user, tenant_id=tenant)

# Create and update records with specific values
emissions1 = EmissionsDataPoint.objects.create(
    tenant_id=tenant,
    facility_name='Factory A',
    scope_1_emissions=100.0,
    reporting_year=2023
)
emissions1.facility_name = 'Factory A (Corrected)'
emissions1.save()

emissions2 = EmissionsDataPoint.objects.create(
    tenant_id=tenant,
    facility_name='Factory B',
    scope_1_emissions=200.0,
    reporting_year=2023
)
```

**Test Steps**:
```python
# 1. Query for records where facility_name changed
from django.db.models import Q

changed_audits = AuditLog.objects.filter(
    object_type='EmissionsDataPoint',
    action='UPDATE'
).exclude(
    change_summary__old_values__facility_name=F('change_summary__new_values__facility_name')
)

print(f"✅ Found {changed_audits.count()} updates where facility_name changed")
assert changed_audits.count() >= 1

# 2. Query for specific old value
audits_with_factory_a = AuditLog.objects.filter(
    change_summary__old_values__facility_name='Factory A'
)
assert audits_with_factory_a.exists()
print("✅ Found audit for 'Factory A' → 'Factory A (Corrected)'")

# 3. Query by JSON path (raw SQL if needed)
audits = AuditLog.objects.raw("""
    SELECT * FROM audit_audit_log
    WHERE object_type = 'EmissionsDataPoint'
    AND action = 'UPDATE'
    AND change_summary->'old_values'->>'facility_name' LIKE '%Factory%'
""")
print(f"✅ Raw SQL query found {len(list(audits))} records")
```

**Expected Output**:
```
✅ JSON queries work with Django ORM
✅ Can find records where specific fields changed
✅ Raw SQL queries also work for complex filters
```

---

## Curl Testing (API Integration Tests)

### Create EmissionsDataPoint via API

```bash
curl -X POST http://localhost:8000/api/emissions/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "facility_name": "Facility Z",
    "scope_1_emissions": 150.5,
    "scope_2_emissions": 50.0,
    "reporting_year": 2023,
    "data_source": "API"
  }'

# Response:
# {
#   "id": "uuid-123",
#   "facility_name": "Facility Z",
#   ...
# }

# Then in database:
# SELECT * FROM audit_audit_log WHERE object_id = 'uuid-123';
# Should return 1 row with action='CREATE'
```

### Query Audit Logs (Future Endpoint, Chunk 2.1)

```bash
curl -X GET http://localhost:8000/api/audit/logs?object_id=uuid-123 \
  -H "Authorization: Bearer <token>"

# Response:
# [
#   {
#     "id": "audit-uuid-1",
#     "action": "CREATE",
#     "timestamp": "2024-05-27T10:00:00Z",
#     "user": "analyst1",
#     "change_summary": {
#       "new_values": {...}
#     }
#   }
# ]
```

---

## Manual Testing Checklist

- [ ] Test 1: Create → AuditLog created
- [ ] Test 2: Update → old vs. new captured
- [ ] Test 3: Delete → AuditLog created
- [ ] Test 4: Query full audit trail
- [ ] Test 5: Tenant isolation works
- [ ] Test 6: Can't update AuditLog (error raised)
- [ ] Test 7: Can't delete AuditLog (error raised)
- [ ] Test 8: Batch operations tracked
- [ ] Test 9: Django admin is read-only
- [ ] Test 10: JSON queries work

---

## Common Issues & Fixes

### Issue: AuditLog not created on save

**Cause**: Signals not registered (app not in INSTALLED_APPS)

**Fix**:
```python
# settings.py
INSTALLED_APPS = [
    ...
    'breathe.apps.audit',  # Add this
    ...
]
```

### Issue: Can't access thread-local context

**Cause**: Middleware not setting audit context

**Fix** (Temporary for testing):
```python
from breathe.apps.audit.signals import set_audit_context
from django.contrib.auth.models import User

user = User.objects.first()
set_audit_context(user=user, tenant_id=tenant, ip_address='127.0.0.1')

# Now create/update records
emissions.save()  # AuditLog will have user/ip/tenant
```

### Issue: "user_id cannot be NULL" error

**Cause**: Trying to save without audit context

**Fix**: Either set audit context or allow user_id to be NULL:
```python
# In signals.py
user_id = models.ForeignKey(
    'auth.User',
    on_delete=models.SET_NULL,
    null=True,  # Allow NULL for system actions
    blank=True
)
```

### Issue: ValueError on save() for existing AuditLog

**Cause**: Accidentally trying to update an audit log

**Expected**: This should fail. Don't update audit logs.

**Solution**: Query it read-only only, never modify.

---

## Success Criteria

✅ All 10 integration tests pass
✅ Django admin shows audit logs read-only
✅ AuditLog entries can't be modified or deleted
✅ Tenant isolation enforced
✅ change_summary JSON properly formatted and queryable
✅ User, IP, timestamp captured correctly
✅ Full audit trail queryable for any record

---

**Version**: May 2026
**Status**: Chunk 1.6 integration tests ready
**Next**: CHUNK_1_6_SUMMARY.md (quick reference)

