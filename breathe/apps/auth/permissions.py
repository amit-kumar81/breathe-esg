"""DRF permission classes for tenant isolation and role-based access."""

from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied


class TenantIsolationPermission(permissions.BasePermission):
    """Ensures a user can only access data belonging to their own tenant."""

    message = "You do not have permission to access data from other tenants."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            request.user.profile
            return True
        except Exception:
            return False

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        try:
            user_tenant_id = request.user.profile.tenant_id
        except Exception:
            return False
        if not hasattr(obj, 'tenant_id'):
            return False
        return obj.tenant_id == user_tenant_id


class IsTenantAdmin(permissions.BasePermission):
    """Allows only tenant admins."""

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
    """Allows analysts and admins."""

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
    """Allows data providers and admins."""

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
    """Mixin that auto-filters ViewSet querysets to the current user's tenant."""

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user or not self.request.user.is_authenticated:
            return queryset.none()
        try:
            tenant_id = self.request.user.profile.tenant_id
        except Exception:
            return queryset.none()
        return queryset.filter(tenant_id=tenant_id)
