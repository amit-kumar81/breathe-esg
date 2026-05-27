"""
Chunk 2.3: Multi-Tenancy Isolation - Permissions

TenantIsolationPermission: Ensures requests are scoped to user's tenant
This is the core of multi-tenancy isolation at the API level.
"""

from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied


class TenantIsolationPermission(permissions.BasePermission):
    """
    Permission check that ensures a user can only access data from their tenant.

    This permission is applied to all viewsets:
    - EmissionsDataPointViewSet
    - ReviewTaskViewSet
    - Any other data-bearing endpoint

    How it works:
    1. Every model has a tenant_id field
    2. When accessing an object (GET /api/emissions/{id}/), check obj.tenant_id == request.user.profile.tenant_id
    3. When listing objects (GET /api/emissions/), filter QuerySet by user's tenant_id
    4. When modifying objects (POST, PATCH, DELETE), check ownership by tenant

    Enforcement Levels:
    - List/Create: Handled in ViewSet.get_queryset() (filters by tenant)
    - Retrieve/Update/Delete: Handled here in has_object_permission()
    - Cross-tenant requests: Raise PermissionDenied
    """

    message = "You do not have permission to access data from other tenants."

    def has_permission(self, request, view):
        """
        List-level permission check.

        Called before any object access.
        At this level, we just check if user is authenticated.
        Filtering by tenant happens in ViewSet.get_queryset().
        """
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Must have a profile (tenant association)
        try:
            request.user.profile  # ← this will raise UserProfile.DoesNotExist if missing
            return True
        except Exception:
            return False

    def has_object_permission(self, request, view, obj):
        """
        Object-level permission check.

        Called when accessing a specific object (/api/emissions/{id}/).
        Ensures obj.tenant_id matches request.user.profile.tenant_id.
        """
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Must have a profile
        try:
            user_tenant_id = request.user.profile.tenant_id
        except Exception:
            return False

        # Check if object has tenant_id attribute
        if not hasattr(obj, 'tenant_id'):
            # If object doesn't have tenant_id, deny access
            # (shouldn't happen if all models are multi-tenant-aware)
            return False

        # Core check: obj's tenant must match user's tenant
        return obj.tenant_id == user_tenant_id


class IsTenantAdmin(permissions.BasePermission):
    """
    Permission check for admin-only actions within a tenant.

    Use for operations like:
    - Managing users in a tenant
    - Viewing audit logs
    - Changing tenant settings

    Example:
    ```python
    class UserManagementViewSet(ModelViewSet):
        permission_classes = [IsAuthenticated, IsTenantAdmin]
    ```
    """

    message = "Only tenant administrators can perform this action."

    def has_permission(self, request, view):
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Must be admin role
        try:
            profile = request.user.profile
            return profile.role == 'ADMIN'
        except Exception:
            return False


class IsAnalyst(permissions.BasePermission):
    """
    Permission check for analyst-only actions.

    Use for review/approval operations:
    - Approving records
    - Rejecting records
    - Requesting clarification

    Example:
    ```python
    class ReviewTaskViewSet(ModelViewSet):
        permission_classes = [IsAuthenticated, TenantIsolationPermission, IsAnalyst]

        @action(detail=True, methods=['post'])
        def approve(self, request, pk):
            # Accessible only to analysts
            ...
    ```
    """

    message = "Only analysts can perform this action."

    def has_permission(self, request, view):
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Must have analyst or admin role
        try:
            profile = request.user.profile
            return profile.role in ['ANALYST', 'ADMIN']
        except Exception:
            return False


class IsDataProvider(permissions.BasePermission):
    """
    Permission check for data provider actions.

    Use for upload/submission operations:
    - Uploading CSV files
    - Submitting data for review

    Example:
    ```python
    class IngestionViewSet(ViewSet):
        permission_classes = [IsAuthenticated, TenantIsolationPermission, IsDataProvider]

        @action(detail=False, methods=['post'])
        def upload(self, request):
            # Accessible only to data providers
            ...
    ```
    """

    message = "Only data providers can perform this action."

    def has_permission(self, request, view):
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Must have data provider or admin role
        try:
            profile = request.user.profile
            return profile.role in ['DATA_PROVIDER', 'ADMIN']
        except Exception:
            return False


class TenantQuerySetMixin:
    """
    Mixin for ViewSets to auto-filter QuerySets by user's tenant.

    Usage:
    ```python
    class EmissionsDataPointViewSet(TenantQuerySetMixin, viewsets.ReadOnlyModelViewSet):
        queryset = EmissionsDataPoint.objects.all()
        serializer_class = EmissionsDataPointDetailSerializer

        # get_queryset() is automatically implemented!
    ```

    The mixin overrides get_queryset() to filter by request.user.profile.tenant_id.
    """

    def get_queryset(self):
        """
        Filter QuerySet by current user's tenant.

        This is the key enforcement point for multi-tenancy.
        Every list request is automatically scoped to the user's tenant.
        """
        queryset = super().get_queryset()

        # Must be authenticated
        if not self.request.user or not self.request.user.is_authenticated:
            return queryset.none()

        # Get user's tenant_id
        try:
            tenant_id = self.request.user.profile.tenant_id
        except Exception:
            return queryset.none()

        # Filter by tenant
        return queryset.filter(tenant_id=tenant_id)
