# Chunk 1.6: Audit Logging (Every Change) — Comprehensive Explanation

## Overview

Chunk 1.6 adds a compliance-grade audit logging system that automatically tracks every change to EmissionsDataPoint, ReviewTask, and NormalizedRecord models. This immutable audit trail is critical for:

- **Regulatory Compliance**: SOX, GDPR, and ESG reporting regulations require proof of data changes
- **Forensic Analysis**: Determine what changed, who changed it, when, and from where
- **Data Quality Assurance**: Detect patterns of analyst bias or approval anomalies
- **Audit Transparency**: Analysts can prove their decisions with full decision history

## Why Audit Logging? (Architectural Rationale)

### The Problem

In production ESG systems, you need answers to compliance questions:

1. **Who approved this emissions record and when?**
2. **What were the original values before the analyst "corrected" them?**
3. **How many times was this record modified?**
4. **Did analyst Jane approve all records from facility X, or did someone else?**
5. **What's the full lineage: CSV → Parsed → Normalized → Approved → Analyzed?**

**Without audit logs**, these questions become impossible to answer. Regulators will reject your compliance claims.

**With audit logs**, you have proof of every decision.

### Why Not Just Query Model History?

**Naive Approach**: "Can't we just query the database for when records changed?"

**Problems**:
- Database doesn't store WHO made the change (user context)
- Database doesn't store the REQUEST CONTEXT (IP, timestamp, tenant)
- Database doesn't capture WHY a change was made (analyst notes)
- Hard to query "what changed on this record over time"
- No enforcement that history can't be deleted

**Better Approach**: Explicit, immutable AuditLog model with full context captured at change time.

## Key Architectural Decisions

### 1. Immutable Append-Only Model (✅ Chosen)

**Decision**: AuditLog can only be created, never updated or deleted.

**Why**:
- Prevents tampering with audit trail (compliance requirement)
- Full audit integrity: you can't cover your tracks
- Ensures historical accuracy

**Implementation**:
```python
def save(self, *args, **kwargs):
    if self.pk and self.id:  # Trying to update
        raise ValueError("AuditLog entries are immutable")
    super().save(*args, **kwargs)

def delete(self, *args, **kwargs):
    raise ValueError("AuditLog entries are immutable")
```

**Rejected Alternatives**:
- ❌ Mutable audit log: Allows deletion/modification (compliance risk)
- ❌ Soft deletes: Still allows updating is_deleted flag (not truly immutable)
- ❌ Database constraints only: Django code can bypass constraints (need both)

### 2. Django Signals for Auto-Logging (✅ Chosen)

**Decision**: Use Django `post_save` and `post_delete` signals to trigger automatic AuditLog creation.

**Why**:
- **Decoupled**: Business logic doesn't know about audit logging
- **Complete**: Every code path that saves a model is logged (no gaps)
- **Consistent**: Same logging logic for all changes
- **Testable**: Can mock signals for unit tests

**How It Works**:
1. View saves EmissionsDataPoint with `instance.save()`
2. Django fires `post_save` signal
3. Signal handler extracts old vs. new values
4. Creates AuditLog entry with change_summary
5. AuditLog is immutable (can't be modified)

**Example**:
```python
@receiver(post_save, sender=EmissionsDataPoint)
def log_emissions_change(sender, instance, created, **kwargs):
    # Automatically called when EmissionsDataPoint is saved
    AuditLog.objects.create(
        object_type='EmissionsDataPoint',
        object_id=str(instance.id),
        action='CREATE' if created else 'UPDATE',
        change_summary={...},
        user_id=context['user'],
        timestamp=now()
    )
```

**Rejected Alternatives**:
- ❌ View-level logging: Requires updating every endpoint (easy to miss)
- ❌ Model.save() override: Still doesn't capture deletes, harder to extend
- ❌ Middleware: Can't distinguish which model changed (too coarse-grained)
- ❌ Database triggers: Not portable across databases, hard to test

### 3. change_summary as JSON (✅ Chosen)

**Decision**: Store old vs. new values in JSONB `change_summary` field.

**Structure**:
```json
{
  "old_values": {
    "facility_name": "Facility A",
    "scope_1_emissions": "100.5",
    "approved_by_id": "user-123"
  },
  "new_values": {
    "facility_name": "Facility A (corrected)",
    "scope_1_emissions": "105.2",
    "approved_by_id": "user-123"
  }
}
```

**Why**:
- **Flexible**: Can handle any model's fields
- **Queryable**: PostgreSQL JSONB supports WHERE clauses
- **Transparent**: Full visibility of what changed
- **Indexable**: Create indexes on specific JSON paths

**Example Query** (Future Analytics):
```sql
SELECT * FROM audit_audit_log
WHERE change_summary->'new_values'->>'facility_name' LIKE '%Facility A%'
AND action = 'UPDATE';
```

**Rejected Alternatives**:
- ❌ Text field "Facility A → Facility A (corrected)": Not queryable
- ❌ Separate old_value/new_value fields: Scales poorly with many fields
- ❌ No change tracking: Lose the "what changed" information

### 4. User Context via Thread-Local Storage (✅ Chosen)

**Decision**: Extract user, IP, tenant from thread-local storage set by middleware.

**Why**:
- **Signal-Friendly**: Signals don't have access to request context
- **Thread-Safe**: Each request has its own thread-local storage
- **Clean**: Decouples signals from request/response cycle

**How It Works**:
```python
# Middleware (to be implemented in Chunk 2.1)
def set_audit_context(request):
    from breathe.apps.audit.signals import set_audit_context
    set_audit_context(
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR'),
        tenant_id=request.user.tenant
    )

# Signal handler (automatically picks up context)
def log_change(sender, instance, **kwargs):
    context = get_audit_context()  # Gets from thread-local
    AuditLog.objects.create(
        user_id=context['user'],
        ip_address=context['ip_address'],
        ...
    )
```

**Rejected Alternatives**:
- ❌ Middleware directly logging: Doesn't capture all changes (API calls, admin panel)
- ❌ Passing user as function argument: Requires refactoring all code
- ❌ Global variable: Not thread-safe

### 5. Tenant Isolation at Model Level (✅ Chosen)

**Decision**: Enforce tenant_id as FK on AuditLog. Analysts can only query their own tenant's logs.

**Why**:
- **Compliance**: Multi-tenancy requirement (Chunk 2.1)
- **Queryable**: Can filter AuditLog.objects.filter(tenant_id=request.user.tenant_id)
- **Performance**: Indexes on tenant_id enable fast queries
- **Immutable**: Can't be changed after creation

**Example**:
```python
class AuditLog(models.Model):
    tenant_id = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    # Analyst can only see:
    # AuditLog.objects.filter(tenant_id=analyst.tenant_id)
```

**Rejected Alternatives**:
- ❌ Row-level security (RLS) only: Still requires code to enforce queries
- ❌ Separate tables per tenant: Can't aggregate across tenants
- ❌ No isolation: Data leak risk

### 6. Separate Audit App (✅ Chosen)

**Decision**: Create dedicated `breathe/apps/audit/` app (models, signals, admin).

**Why**:
- **Reusable**: Audit logging is generic, can extend to other models later
- **Isolated**: Doesn't pollute other app namespaces
- **Maintainable**: Easy to find all audit-related code
- **Testable**: Can test audit logic independently

**Rejected Alternatives**:
- ❌ Audit logging in each app: Duplicate code, inconsistent
- ❌ Single large utils.py: Becomes unmanageable over time

## Implementation Walkthrough

### 1. AuditLog Model (models.py)

```python
class AuditLog(models.Model):
    id = UUIDField()  # Unique identifier
    object_type = CharField()  # "EmissionsDataPoint", "ReviewTask", etc.
    object_id = CharField()  # UUID of the object being audited
    tenant_id = ForeignKey(Tenant)  # Multi-tenancy isolation
    action = CharField(choices=CREATE/UPDATE/DELETE)
    change_summary = JSONField()  # {"old_values": {...}, "new_values": {...}}
    user_id = ForeignKey(User)  # Who made the change
    timestamp = DateTimeField()  # When (auto_now_add=True)
    ip_address = CharField()  # From where (optional)
```

**Immutability Enforcement**:
- `save()` method checks if `self.pk` exists (update attempt)
- `delete()` method always raises ValueError
- Result: Can only INSERT, never UPDATE or DELETE

### 2. Django Signals (signals.py)

**Post-Save Handler**:
```python
@receiver(post_save, sender=EmissionsDataPoint)
def log_change(sender, instance, created, **kwargs):
    action = 'CREATE' if created else 'UPDATE'
    
    if not created:
        # For updates, fetch old instance to compare
        old_instance = EmissionsDataPoint.objects.get(pk=instance.pk)
        change_summary = get_changed_fields(instance, old_instance)
    else:
        # For creates, only new_values
        change_summary = {'new_values': serialize(instance)}
    
    AuditLog.objects.create(
        object_type='EmissionsDataPoint',
        object_id=str(instance.id),
        action=action,
        change_summary=change_summary,
        ...
    )
```

**Post-Delete Handler**:
```python
@receiver(post_delete, sender=EmissionsDataPoint)
def log_delete(sender, instance, **kwargs):
    AuditLog.objects.create(
        action='DELETE',
        change_summary={'old_values': serialize(instance)},
        ...
    )
```

### 3. Thread-Local Context (signals.py)

```python
_thread_locals = local()

def set_audit_context(user=None, ip_address=None, tenant_id=None):
    _thread_locals.user = user
    _thread_locals.ip_address = ip_address
    _thread_locals.tenant_id = tenant_id

def get_audit_context():
    return {
        'user': getattr(_thread_locals, 'user', None),
        'ip_address': getattr(_thread_locals, 'ip_address', None),
        'tenant_id': getattr(_thread_locals, 'tenant_id', None),
    }
```

**Usage in Middleware** (Chunk 2.1):
```python
class AuditContextMiddleware:
    def __call__(self, request):
        set_audit_context(
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            tenant_id=request.user.tenant_id if request.user.is_authenticated else None
        )
        return self.get_response(request)
```

### 4. Signal Registration (apps.py)

```python
class AuditConfig(AppConfig):
    name = 'breathe.apps.audit'
    
    def ready(self):
        import breathe.apps.audit.signals  # Register handlers
```

**Why `ready()`?**: Ensures signals are registered before Django processes models.

### 5. Admin Interface (admin.py)

```python
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action_badge', 'object_type', 'user', 'tenant')
    list_filter = ('action', 'object_type', 'tenant_id', 'timestamp')
    search_fields = ('object_id', 'user_id__username')
    readonly_fields = (...)  # All fields are read-only
    
    # Disable add/edit/delete
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
```

## Interview Questions & Answers

### Q1: How do we prevent analysts from deleting their own audit logs?

**A**: Multiple layers of protection:

1. **Model-level**: `delete()` method raises ValueError
2. **Django admin**: `has_delete_permission()` returns False
3. **Database**: Can add CHECK constraint (append-only)
4. **Permissions**: Only superuser can access audit logs (Chunk 2.1)

Example:
```python
try:
    audit_log.delete()  # Raises ValueError
except ValueError as e:
    print(e)  # "AuditLog entries cannot be deleted"
```

**Compliance**: This satisfies SOX requirement of immutable audit trails.

---

### Q2: What if the user is deleted but we have their audit logs?

**A**: `user_id` is nullable and uses `on_delete=models.SET_NULL`:

```python
user_id = ForeignKey(
    'auth.User',
    on_delete=models.SET_NULL,
    null=True
)
```

Result:
- User gets deleted
- `AuditLog.user_id` becomes NULL
- Audit log remains (user_id=None means "deleted user")
- We still know WHEN and WHAT changed, just not WHO (by name)
- Optional: Store username as string in change_summary before deletion

**Better approach** (Chunk 2.1):
```python
change_summary = {
    'user_name': instance.user.username,  # Store for posterity
    'user_id': str(instance.user.id),
    ...
}
```

---

### Q3: How do we capture IP address?

**A**: From Django request via thread-local storage:

```python
# Middleware
ip = request.META.get('REMOTE_ADDR')  # Client IP
# or
ip = request.META.get('HTTP_X_FORWARDED_FOR')  # Behind proxy

# Store in thread-local
set_audit_context(ip_address=ip)

# Signal picks it up
context = get_audit_context()
AuditLog.objects.create(ip_address=context['ip_address'])
```

**Edge cases**:
- Behind load balancer: Use X-FORWARDED-FOR header
- IPv6 addresses: CharField(max_length=45) supports both IPv4 (15) and IPv6 (45)
- No request context (management command): ip_address stays NULL

---

### Q4: What if we need to audit the audit system itself?

**A**: Good question! But we don't. Here's why:

1. **AuditLog is append-only**: Can't be modified, so no need to audit changes
2. **Can't be deleted**: So deletion attempts are caught at application level
3. **Database backup**: PostgreSQL WAL (Write-Ahead Logging) tracks all changes to audit_audit_log table

If we want meta-auditing:
```python
# Log attempts to delete/modify audit logs (which will fail)
@receiver(pre_delete, sender=AuditLog)
def prevent_audit_deletion(sender, instance, **kwargs):
    # Log the attempted deletion
    MetaAuditLog.objects.create(
        attempted_action='DELETE_AUDIT',
        blocked=True,
        user_id=get_audit_context()['user']
    )
```

But for MVP, the immutability + database backups are sufficient.

---

### Q5: How do we handle timezone issues in audit timestamps?

**A**: Use Django's auto_now_add with settings.TIME_ZONE:

```python
# settings.py
USE_TZ = True  # Use UTC in database
TIME_ZONE = 'UTC'  # Store all times as UTC

# Model
timestamp = DateTimeField(auto_now_add=True)  # Automatically UTC

# When querying
from django.utils import timezone
now = timezone.now()  # Returns aware datetime in settings.TIME_ZONE
```

**In serializer** (Chunk 2.1):
```python
class AuditLogSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(format='iso-8601')
    # Returns: "2024-05-27T10:30:45Z" (always UTC)
```

**For analyst viewing** (Chunk 2.3):
```javascript
// Frontend (React)
const localTime = new Date(audit.timestamp);
return localTime.toLocaleString();  // Converts to browser's timezone
```

---

### Q6: What if a signal handler fails?

**A**: The signal failure will propagate and block the model save:

```python
# If signal raises exception
@receiver(post_save, sender=EmissionsDataPoint)
def log_change(sender, instance, **kwargs):
    AuditLog.objects.create(...)  # If this fails, model.save() fails

# The model won't be saved if audit logging fails
# Result: Data integrity (either save + audit both succeed, or both fail)
```

**Best Practice**: Wrap signal in try/except to fail gracefully:

```python
@receiver(post_save, sender=EmissionsDataPoint)
def log_change(sender, instance, **kwargs):
    try:
        AuditLog.objects.create(...)
    except Exception as e:
        logger.error(f"Audit logging failed: {e}")
        # Decide: fail silently (data saved) or re-raise (data not saved)
```

**Trade-off**:
- **Fail silently**: Data is saved but not logged (audit gap)
- **Re-raise**: Data not saved but audit is guaranteed (can be annoying for users)
- **Queue to celery**: Log asynchronously (best of both, but added complexity)

**MVP approach**: Fail silently with logging (Chunk 1.6). Upgrade to queue-based in production.

---

### Q7: How do we query audit logs efficiently?

**A**: Use indexed fields:

```python
# Slow (no index on object_id alone in multi-tenant)
AuditLog.objects.filter(object_id='123')

# Fast (uses index on (tenant_id, object_id))
AuditLog.objects.filter(
    tenant_id=request.user.tenant_id,
    object_id='123'
)

# Fast (uses index on (object_type, object_id))
AuditLog.objects.filter(
    object_type='EmissionsDataPoint',
    object_id='123'
)

# Slow (no index on timestamp alone)
AuditLog.objects.filter(timestamp__gte=date)

# Fast (uses index on timestamp)
AuditLog.objects.filter(
    timestamp__gte=date,
    timestamp__lte=date_end
)
```

**Database indexes** (models.py):
```python
indexes = [
    models.Index(fields=['tenant_id']),
    models.Index(fields=['object_type', 'object_id']),
    models.Index(fields=['action']),
    models.Index(fields=['timestamp']),
]
```

---

### Q8: How do we handle bulk operations?

**A**: Django signals fire per-instance:

```python
# Bulk create: No post_save signal
EmissionsDataPoint.objects.bulk_create([obj1, obj2, obj3])
# ❌ AuditLog NOT created

# Bulk update: No post_save signal
EmissionsDataPoint.objects.filter(...).update(field='value')
# ❌ AuditLog NOT created
```

**Solution**: Loop and save individually, or override `bulk_create`:

```python
# Better: Save one-by-one (slower but auditable)
for obj in [obj1, obj2, obj3]:
    obj.save()  # post_save signal fires, AuditLog created

# Or: Override bulk operations
class EmissionsDataPointManager(models.Manager):
    def bulk_create(self, objs, **kwargs):
        objs = super().bulk_create(objs, **kwargs)
        for obj in objs:
            post_save.send(EmissionsDataPoint, instance=obj, created=True)
        return objs
```

**Trade-off**: Bulk operations are slower but more auditable.

---

### Q9: Can we query JSON nested values efficiently?

**A**: Yes, PostgreSQL JSONB supports queries:

```python
# Django ORM query
from django.db.models import F, Q
from django.db.models.functions import JSONExtract

# Find records where facility_name changed
AuditLog.objects.filter(
    change_summary__old_values__facility_name__isnull=False,
    change_summary__new_values__facility_name__isnull=False
).exclude(
    change_summary__old_values__facility_name=F('change_summary__new_values__facility_name')
)

# Raw SQL (faster for complex queries)
AuditLog.objects.raw("""
    SELECT * FROM audit_audit_log
    WHERE change_summary->'old_values'->>'facility_name' != 
          change_summary->'new_values'->>'facility_name'
    AND action = 'UPDATE'
""")
```

**Performance**: For analytics, consider materialized views or background jobs (Chunk 2.2+).

---

### Q10: How do we prevent a replay attack where someone re-plays an audit log?

**A**: Audit logs are immutable and append-only:

1. **Can't delete**: So attacker can't remove evidence
2. **Can't modify**: So attacker can't change WHAT was done
3. **Timestamp is immutable**: So attacker can't change WHEN
4. **User is recorded**: So we know WHO did it
5. **IP is recorded**: So we know FROM WHERE

**Defense in depth**:
```python
# Layer 1: Immutable model
AuditLog.delete()  # Raises ValueError

# Layer 2: Django permission
AuditLogAdmin.has_delete_permission()  # Returns False

# Layer 3: Database constraint (future)
ALTER TABLE audit_audit_log ADD CONSTRAINT audit_immutable CHECK (created_at IS NOT NULL);

# Layer 4: Access control
# Only view audit logs if user.is_superuser (Chunk 2.1)
```

**To prevent replay attacks** (changing data based on old values):
```python
# Bad: Replay an old approval
old_audit = AuditLog.objects.filter(
    object_type='EmissionsDataPoint',
    action='UPDATE',
    change_summary__new_values__approved=True
).first()
# Then re-apply those changes...

# Good: Reject if current version != version in audit log
current = EmissionsDataPoint.objects.get(id=audit_log.object_id)
if current.version != audit_log.change_summary['old_values']['version']:
    raise ReplayAttackDetected()
```

---

## File Organization

```
breathe/apps/audit/
├── __init__.py          # App initialization
├── models.py            # AuditLog model (immutable)
├── signals.py           # Signal handlers for post_save/post_delete
├── admin.py             # Django admin (read-only)
├── apps.py              # AppConfig with ready() for signal registration
└── migrations/          # Django migrations (auto-generated)
    └── 0001_initial.py
```

## Data Flow

```
View saves EmissionsDataPoint
    ↓
EmissionsDataPoint.save() called
    ↓
Django post_save signal fired
    ↓
log_emissions_data_point_change() handler
    ↓
Fetch context from thread-local (user, ip, tenant)
    ↓
Serialize old values (if UPDATE)
    ↓
Create AuditLog entry (immutable)
    ↓
Analyst can query: AuditLog.objects.filter(object_id='...')
    ↓
See full change history with WHO, WHAT, WHEN, WHERE
```

## Success Criteria

✅ Every EmissionsDataPoint creation is logged with action='CREATE'
✅ Every EmissionsDataPoint update is logged with action='UPDATE', showing old vs. new values
✅ Every EmissionsDataPoint deletion is logged with action='DELETE'
✅ Analysts can query audit trail for a specific record: `AuditLog.objects.filter(object_id='...')`
✅ AuditLog entries can't be modified (save() raises error)
✅ AuditLog entries can't be deleted (delete() raises error)
✅ Audit logs are tenant-isolated (analysts only see their own tenant's logs)
✅ Django admin shows all audit entries in read-only mode
✅ change_summary JSON captures full before/after state
✅ User context (who made the change) is captured
✅ IP address is captured for forensic analysis

## Testing Strategy (Chunk 1.6 Integration Guide)

10 integration tests:
1. Create EmissionsDataPoint → AuditLog created with CREATE action
2. Update EmissionsDataPoint → AuditLog shows old vs. new values
3. Delete EmissionsDataPoint → AuditLog created with DELETE action
4. Query audit trail for specific record
5. Verify analyst can only see own tenant's audit logs
6. Attempt to update AuditLog → ValueError raised
7. Attempt to delete AuditLog → ValueError raised
8. Batch operations tracked (one AuditLog per item)
9. Django admin view shows all audit entries (read-only)
10. change_summary JSON properly formatted and queryable

## Next Steps (Chunk 2.1: Real Authentication)

- Implement AuditContextMiddleware to set user/ip/tenant
- Replace request.tenant_id placeholders with request.user.tenant_id
- Implement JWT auth for API endpoints
- Add permission checks (only superuser can view audit logs)
- Create API endpoint: GET /api/audit/logs?object_id=... (paginated)

---

**Version**: May 2026
**Status**: Chunk 1.6 architecture complete, ready for implementation
**Next**: CHUNK_1_6_INTEGRATION_GUIDE.md with test cases

