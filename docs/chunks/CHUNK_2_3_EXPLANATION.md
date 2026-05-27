# Chunk 2.3: Multi-Tenancy Isolation - Detailed Explanation

## Overview

Chunk 2.3 implements **multi-tenancy isolation** at the API layer using JWT authentication and row-level permission checks. Each user is associated with exactly one tenant (organization). All data queries are automatically scoped to that user's tenant, preventing cross-tenant data leakage.

---

## Architecture Decision 1: JWT Over Session Authentication

### The Decision
We use **JWT (JSON Web Tokens)** instead of Django's built-in session authentication.

```python
# JWT: Stateless, token includes claims
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {"username": "alice", "tenant_id": "abc-123", "role": "ANALYST"}
}

# Session: Stateful, server stores session data
{
  "session_id": "abc123xyz",
  # Server has: {session_id: {user_id, tenant_id, role}} in database
}
```

### Why This Decision

**Stateless Scalability**: With JWT, there's no session table. Each token is self-contained. A request to any server (1, 2, 3, or 100) can validate the token locally without querying the database.

```
Session-based:
Request to Server 1 → Lookup session_id in database → Verify user
Request to Server 2 → Same lookup → Verify user
Scaling: Need shared session store (Redis, database)

JWT-based:
Request to Server 1 → Verify token signature locally → Done
Request to Server 2 → Verify token signature locally → Done
Scaling: No shared state needed
```

**Mobile-Friendly**: Mobile apps store tokens in local storage. Sessions require cookie-based flows which are complex on mobile.

**Embedded Context**: JWT token includes `tenant_id` and `role` in claims. No need to look up UserProfile on every request. Token can be decoded to get context.

**Compliance**: JWT tokens have expiration built-in. After 15 minutes, token is invalid. Forces re-authentication, improves security. Sessions can be indefinitely long if not managed.

### Alternative Considered: Sessions
```python
# Django sessions + database lookup
request.session = {"user_id": 1, "tenant_id": "abc-123"}
# Server must query database to validate on each request
```

**Why Rejected**: Requires session table (another database table to manage), scales poorly across multiple servers, no built-in expiration, less mobile-friendly.

---

## Architecture Decision 2: UserProfile Model Instead of User Modification

### The Decision
We don't modify Django's `User` model. Instead, we create a separate `UserProfile` model with a OneToOne relationship to `User`.

```python
# ✅ Correct: Separate profile
class User(models.Model):  # Django built-in
    username = CharField()
    password = CharField()

class UserProfile(models.Model):  # Our custom model
    user = OneToOneField(User)
    tenant = ForeignKey(Tenant)
    role = CharField(choices=['ADMIN', 'ANALYST', ...])
```

NOT:
```python
# ❌ Wrong: Modify Django User
class User(models.Model):
    username = CharField()
    password = CharField()
    tenant = ForeignKey(Tenant)  # ← Modifying Django's User
    role = CharField()
```

### Why This Decision

**Compatibility**: Django's User model is used by:
- Django admin
- Django's built-in authentication
- Third-party packages (django-rest-framework, django-allauth, etc.)

Modifying it breaks assumptions in these packages. Separating concerns keeps User clean.

**Flexibility**: A UserProfile can reference a Tenant. If you later want a user in multiple tenants, you can create UserProfile2 with different tenant. The User remains singular.

**Minimal Coupling**: If we ever migrate authentication systems (OAuth, LDAP, SSO), the User model might change. UserProfile stays the same.

**Inheritance Pattern**: This is the standard Django pattern. User is identity. UserProfile is application-specific context (tenant, role).

### Alternative Considered: AbstractBaseUser
```python
# Create custom user model with tenant_id
class CustomUser(AbstractBaseUser):
    username = CharField()
    tenant = ForeignKey(Tenant)
    role = CharField()
```

**Why Rejected**: Requires `AUTH_USER_MODEL = 'myapp.CustomUser'` in settings. All migrations depend on it. Harder to integrate with third-party packages that expect Django's User. More work to set up initially.

---

## Architecture Decision 3: Tenant-Based Isolation, Not Schema-Based

### The Decision
All tenants share the same database schema. Isolation is enforced by `tenant_id` column and filtering QuerySets.

```python
# All data in one table, tenant_id distinguishes
EmissionsDataPoint:
  id | tenant_id       | facility_name | scope_1_emissions
  1  | abc-123 (Acme)  | Plant A       | 500
  2  | def-456 (Beta)  | Plant B       | 600

Query for Acme user:
EmissionsDataPoint.objects.filter(tenant_id='abc-123')
→ Returns only row 1
```

NOT:
```python
# Schema-based isolation (separate schemas per tenant)
acme.public.EmissionsDataPoint:
  id | facility_name | scope_1_emissions
  1  | Plant A       | 500

beta.public.EmissionsDataPoint:
  id | facility_name | scope_1_emissions
  2  | Plant B       | 600

# Would require tenant-aware connection switching
```

### Why This Decision

**Simpler Implementation**: No connection switching per request. One database connection, filter by column. All standard Django ORM.

**Lower Maintenance**: One set of migrations. Easier schema updates. If you add a column, it's one migration, not 100+ migrations per tenant.

**Cost**: One database, one set of indexes. Schema-based multi-tenancy requires separate connections or schemas per tenant (storage overhead).

**Row-Level Encryption** (Future): If you later want encryption at the database level, you can add a `decrypt(sensitive_field)` wrapper. Schema-based doesn't help with encryption; you need column-level anyway.

### Real-World Trade-Off
```
Shared Schema (Row-Level) Isolation:
+ Simple, one database
+ Cheap to operate
- Relies on code to enforce isolation (developer responsibility)
- One bug and all tenants leak

Schema-Based Isolation:
+ Automatic isolation (different schemas)
- Complex, multiple connections
- Expensive (multiple database objects)
- Still need row-level security if schemas are breached

Decision: Start with shared schema (simpler, cheaper).
If isolation requirements get stricter, migrate to schema-based later.
```

---

## Architecture Decision 4: TenantQuerySetMixin for Auto-Filtering

### The Decision
Every ViewSet that needs multi-tenancy inherits from `TenantQuerySetMixin`, which overrides `get_queryset()` to filter by `user.profile.tenant_id`.

```python
class TenantQuerySetMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant_id = self.request.user.profile.tenant_id
        return queryset.filter(tenant_id=tenant_id)

# Usage:
class EmissionsDataPointViewSet(TenantQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = EmissionsDataPoint.objects.all()
    # get_queryset() is inherited and auto-filters by tenant
```

### Why This Decision

**DRY (Don't Repeat Yourself)**: Without the mixin, every ViewSet would need:
```python
def get_queryset(self):
    return EmissionsDataPoint.objects.filter(
        tenant_id=self.request.user.profile.tenant_id
    )
```

Repeated 10+ times across the codebase. Mixin centralizes the pattern.

**Consistency**: All ViewSets use the same filtering logic. A developer adding a new ViewSet just inherits the mixin—no manual filtering needed.

**Default Security**: Mixin makes "secure by default". Forgetting to filter is a bug in the mixin (which exists in one place), not a bug per ViewSet.

### Alternative Considered: Manual Filtering in Each ViewSet
```python
class EmissionsDataPointViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmissionsDataPoint.objects.all()
    
    def get_queryset(self):
        return self.queryset.filter(
            tenant_id=self.request.user.profile.tenant_id
        )

# Same for ReviewTaskViewSet, IngestionViewSet, ...
```

**Why Rejected**: Repetition across 10+ ViewSets. Easy to forget. Single point of failure: if a developer forgets the filter, data leaks.

---

## Architecture Decision 5: TenantIsolationPermission for Object-Level Checks

### The Decision
After a QuerySet is filtered by tenant, we add an object-level permission check: `TenantIsolationPermission.has_object_permission()`.

```python
class TenantIsolationPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user_tenant_id = request.user.profile.tenant_id
        return obj.tenant_id == user_tenant_id

# Usage:
class ReviewTaskViewSet(viewsets.ModelViewSet):
    permission_classes = [TenantIsolationPermission]
    # Now GET /api/review/123/ checks if review task 123 belongs to user's tenant
```

### Why This Decision

**Defense in Depth**: Two layers of isolation:
1. QuerySet filtering: Prevents listing other tenants' data
2. Object-level permission: Prevents direct ID access to other tenants' objects

If a bug in get_queryset() slips past code review, the permission class still blocks it.

**Catches Edge Cases**: Some endpoints might build custom QuerySets or caching. Permission check catches those too.

**RESTful Best Practice**: DRF expects permission checks at object level for RETRIEVE, UPDATE, DELETE operations. Implementing it is standard.

### Example Defense-in-Depth
```
User A tries to GET /api/review/456/ (User B's task)

1. TenantQuerySetMixin.get_queryset()
   → filter(tenant_id=user_a_tenant)
   → Doesn't include task 456 (belongs to user_b_tenant)

2. But if API allows direct ID access (custom endpoint):
   → TenantIsolationPermission.has_object_permission()
   → Checks task_456.tenant_id == user_a.profile.tenant_id
   → Returns False
   → 403 Forbidden

Without permission check:
   → Task 456 loaded from database
   → Returned to User A
   → DATA LEAK!
```

---

## Architecture Decision 6: Role-Based Permissions (ADMIN, ANALYST, DATA_PROVIDER)

### The Decision
We define roles in UserProfile and create permission classes for each role.

```python
class UserProfile(models.Model):
    role = CharField(choices=[
        'ADMIN',           # Full access
        'ANALYST',         # Can approve/reject records
        'DATA_PROVIDER',   # Can upload data
        'VIEWER'           # Read-only access
    ])

# Permission classes:
class IsAnalyst(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.profile.role in ['ANALYST', 'ADMIN']

class IsDataProvider(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.profile.role in ['DATA_PROVIDER', 'ADMIN']
```

### Why This Decision

**Granular Access Control**: Not all users can do all actions.
- Analysts approve records
- Data providers upload data
- Admins manage users
- Viewers only read data

**Flexibility**: Roles can be extended without code changes. Add 'QA_MANAGER' role, define IsQAManager permission.

**Future Compliance**: ESG reporting often requires role segregation for compliance (audit trails show who did what).

### Example Usage
```python
# Only analysts can approve
class ReviewTaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, TenantIsolationPermission, IsAnalyst]

    @action(detail=True, methods=['post'])
    def approve(self, request, pk):
        # Only accessible to analysts
        ...

# Only data providers can upload
class IngestionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, TenantIsolationPermission, IsDataProvider]

    @action(detail=False, methods=['post'])
    def upload(self, request):
        # Only accessible to data providers
        ...
```

### Alternative Considered: Single Role (Everyone Can Do Everything)
```python
class ReviewTaskViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    # No role check; anyone can approve
```

**Why Rejected**: No separation of duties. Data providers could approve their own invalid data. Analysts could upload data and then approve it (fraud). Compliance requires role segregation.

---

## Architecture Decision 7: JWT Embedding Tenant_ID in Token Claims

### The Decision
When a user logs in, the JWT token includes `tenant_id` and `role` in the payload (claims).

```python
# LoginView creates token with custom claims
refresh = RefreshToken.from_user(user)
refresh['tenant_id'] = str(profile.tenant_id)
refresh['role'] = profile.role
# Token now includes: {"user_id": 1, "tenant_id": "abc-123", "role": "ANALYST"}
```

### Why This Decision

**Performance**: Frontend or middleware can extract `tenant_id` from token without database query.

```python
# Without embedded tenant_id:
def get_queryset(self):
    # Must query database
    user_profile = request.user.profile  # ← Database query
    return QuerySet.filter(tenant_id=user_profile.tenant_id)

# With embedded tenant_id:
def get_queryset(self):
    # Token is decoded, tenant_id is in claims
    tenant_id = request.auth['tenant_id']  # ← No database query
    return QuerySet.filter(tenant_id=tenant_id)
```

**Debugging**: Token claims are visible in logs, tools like jwt.io. Easier to debug auth issues.

**Frontend Awareness**: JavaScript frontend can decode token (no need for server call to /api/auth/me/) and know the user's tenant immediately.

### Alternative Considered: Store Only User_ID
```python
# Token includes only user_id
# Server must query UserProfile.tenant_id on each request
refresh = RefreshToken.from_user(user)
# Token: {"user_id": 1}
```

**Why Rejected**: Extra database query on every request. Unnecessary load. Embedding tenant_id is standard JWT practice.

---

## Architecture Decision 8: Login Returns User Profile + Tokens

### The Decision
`POST /api/auth/login/` returns access token, refresh token, AND user profile data.

```python
# Response:
{
  "access": "eyJ0eXAi...",
  "refresh": "eyJ0eXAi...",
  "user": {
    "username": "alice",
    "email": "alice@example.com",
    "tenant": {"id": "abc-123", "name": "Acme Corp"},
    "role": "ANALYST"
  }
}
```

### Why This Decision

**Single Request**: Frontend gets everything in one login request. Can display user name, tenant name, permissions immediately without calling `/api/auth/me/`.

**Context Availability**: Frontend knows which tenant it's serving. Can set headers, adjust UI, etc. immediately after login.

**Backwards Compatibility**: If frontend previously had `/api/auth/me/` endpoint, this reduces number of requests.

### Alternative Considered: Return Only Tokens
```python
# Response:
{
  "access": "eyJ0eXAi...",
  "refresh": "eyJ0eXAi..."
}
# Frontend must call GET /api/auth/me/ separately
```

**Why Rejected**: Extra request, worse UX. Login should be one round-trip.

---

## Architecture Decision 9: Middleware vs. Permission Class for Tenant Context

### The Decision
We use a **permission class**, not middleware, to set and check tenant context.

```python
# ✅ Permission class:
class TenantIsolationPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.tenant_id == request.user.profile.tenant_id

# ❌ NOT middleware:
class TenantMiddleware:
    def __call__(self, request):
        request.tenant_id = request.user.profile.tenant_id
        # Then manually check in views
```

### Why This Decision

**DRF Integration**: Permission classes are built into DRF's request/response cycle. DRF calls `has_permission()` and `has_object_permission()` automatically.

**Testability**: Permission classes are unit-testable. Middleware is tested in integration tests.

**Clarity**: Permission classes declare what permissions are needed. Middleware is implicit and easy to miss.

**Reusability**: Permission classes work with DRF, GraphQL, or any layer. Middleware is specific to HTTP.

### Alternative Considered: Middleware
```python
class TenantContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        request.tenant_id = request.user.profile.tenant_id
        response = self.get_response(request)
        return response
```

**Why Rejected**: Implicit and easy to forget. Doesn't integrate with DRF's permission system. Harder to test.

---

## Architecture Decision 10: No Token Blacklist (For MVP)

### The Decision
On logout, we do NOT blacklist the token. The token remains valid until it expires (15 min for access, 7 days for refresh).

```python
# LogoutView doesn't actually invalidate the token
class LogoutView(APIView):
    def post(self, request):
        # No blacklisting. Token is still valid.
        return Response({'message': 'Logged out'})

# If attacker steals token, they can use it for 15 minutes anyway.
# This is acceptable for MVP. Better to implement later if needed.
```

### Why This Decision

**Simplicity**: Token blacklist requires a table (BlacklistedToken) to store revoked tokens. Every request checks if token is blacklisted. Adds database query to every authenticated request.

**Stateless JWT Contradiction**: JWT is stateless. Blacklist makes it stateful. Defeats the purpose.

**Short-Lived Tokens**: Access token lasts 15 minutes. If a user logs out, the token becomes useless in 15 minutes anyway. For web apps, this is acceptable.

**Production Warning**: For highly secure applications (banking, healthcare), implement token blacklist. For MVP ESG platform, defer this.

### How to Implement Later
```python
# In models.py
class BlacklistedToken(models.Model):
    token = CharField(max_length=500, unique=True)
    blacklisted_at = DateTimeField(auto_now_add=True)

# In permission class
def has_permission(self, request, view):
    if BlacklistedToken.objects.filter(token=str(request.auth)).exists():
        return False
    return True
```

---

## Architecture Decision 11: TenantAwareManager for Custom QuerySets

### The Decision
For complex queries, create a custom Manager that filters by tenant automatically.

```python
class TenantAwareManager(models.Manager):
    def for_tenant(self, tenant_id):
        return self.filter(tenant_id=tenant_id)

class EmissionsDataPoint(models.Model):
    objects = TenantAwareManager()
    
    # Now:
    EmissionsDataPoint.objects.for_tenant(request.user.profile.tenant_id)
    # Instead of:
    EmissionsDataPoint.objects.filter(tenant_id=request.user.profile.tenant_id)
```

### Why This Decision

**Convenience**: Custom manager method `for_tenant()` is more readable than filter.

**DRY**: Common pattern centralized in manager. Used across queries.

**Future Expansion**: Manager can add other methods like `for_analyst(user)`, `recent(days=7)`, etc.

### Alternative Considered: Only Use TenantQuerySetMixin
```python
# Just rely on TenantQuerySetMixin in ViewSets
# Don't need custom manager
```

**Why Not Rejected**: TenantAwareManager is optional but useful for shell commands, management commands, background tasks that need manual tenant filtering. Mixin only works in ViewSets.

---

## Architecture Decision 12: Tenant_ID on Every Model (Denormalization)

### The Decision
Every model that holds data has a `tenant_id` field, even if it could be derived through relations.

```python
# ✅ Every model has tenant_id
class EmissionsDataPoint(models.Model):
    tenant_id = UUIDField()  # Direct column
    normalized_record = ForeignKey(NormalizedRecord)

class ReviewTask(models.Model):
    tenant_id = UUIDField()  # Direct column (could get from normalized_record.tenant_id)
    normalized_record = ForeignKey(NormalizedRecord)

# ❌ NOT just relying on relations
class ReviewTask(models.Model):
    # tenant_id removed, would get from normalized_record
    normalized_record = ForeignKey(NormalizedRecord)
    
    @property
    def tenant_id(self):
        return self.normalized_record.tenant_id  # ← Requires join
```

### Why This Decision

**Query Performance**: Filtering by tenant_id is a direct column lookup. No joins needed.
```python
# Fast: Direct column filter
ReviewTask.objects.filter(tenant_id='abc-123')

# Slow: Join to get tenant_id
ReviewTask.objects.filter(normalized_record__tenant_id='abc-123')
```

**Isolation**: Tenant_ID on every model makes isolation obvious. Any query can filter directly.

**Consistency**: All models have the same isolation pattern. No surprises.

**Index Strategy**: tenant_id is indexed on every model for fast filtering. Derived property can't be indexed.

### Trade-Off: Denormalization Complexity
```
Pro: Faster queries, clearer isolation
Con: Redundant column (tenant_id on ReviewTask when already on NormalizedRecord)
Con: Must update tenant_id consistently when relations change

Decision: For multi-tenancy, denormalization is worth the cost.
```

---

## Summary of Decisions

| Decision | Why | Trade-Off |
|----------|-----|-----------|
| JWT | Stateless, scalable, mobile-friendly | No session table, need token refresh |
| UserProfile | Separate from User | Extra model, OneToOne relation |
| Shared Schema | Simple, cheap | Relies on code enforcement |
| TenantQuerySetMixin | DRY, consistent | One inheritance requirement |
| TenantIsolationPermission | Defense in depth | Two isolation layers |
| Role-Based Permissions | Granular access | More permission classes to define |
| Embedded Tenant_ID in Token | Performance | Tokens are larger |
| Return Profile on Login | Single request | Slightly larger response |
| Permission Classes | DRF integration | Not middleware-based |
| No Token Blacklist | Simplicity | Compromised tokens valid for 15 min |
| TenantAwareManager | Convenience | Optional, adds method |
| Tenant_ID on Every Model | Query performance | Denormalization, consistency |

---

## Key Principles

1. **Isolation by Default**: Every query filtered by tenant unless explicitly bypassed
2. **Defense in Depth**: Multiple layers (QuerySet filter + Permission check)
3. **Stateless JWT**: No server state, scales horizontally
4. **Role Segregation**: Users have roles, permissions are role-based
5. **Data Consistency**: Tenant_ID on every model ensures consistency
6. **MVP Pragmatism**: Token blacklist deferred, shared schema sufficient for now

---

## Testing Strategy

This chunk is validated through 10+ integration tests (see INTEGRATION_GUIDE):

1. **Login Returns Tokens**: POST /api/auth/login/ returns access + refresh
2. **Token Includes Tenant_ID**: Decode token, tenant_id is in claims
3. **Refresh Token Works**: POST /api/auth/refresh/ returns new access token
4. **Current User Endpoint**: GET /api/auth/me/ returns user profile
5. **User A Can't See User B's Data**: GET /api/emissions/ only returns User A's tenant data
6. **User A Can't Access User B's Object**: GET /api/emissions/{user_b_id}/ returns 403
7. **Analyst Can Approve**: IsAnalyst permission allows POST approve()
8. **Data Provider Can Upload**: IsDataProvider permission allows POST upload()
9. **Viewer Can't Approve**: IsViewer permission blocks POST approve()
10. **Token Expiry**: After 15 minutes, access token is invalid
11. **Refresh Extends**: Refresh token (7 days) refreshes access token multiple times
12. **Tenant Isolation in Batch**: Batch operation respects tenant_id filtering

---

This chunk is the foundation of multi-tenancy. All subsequent chunks assume isolation is working correctly.
