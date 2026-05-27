"""
Chunk 2.3: Multi-Tenancy Isolation - Auth Admin

Django admin interface for managing tenants and user profiles.
"""

from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'tenant', 'role', 'is_active', 'created_at']
    list_filter = ['tenant', 'role', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__email', 'tenant__name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('User Association', {
            'fields': ('user', 'tenant')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """
        Admin users see all profiles.
        Tenant admins see only profiles in their tenant.
        """
        queryset = super().get_queryset(request)

        # If user is not superuser, filter by their tenant
        if not request.user.is_superuser:
            try:
                tenant_id = request.user.profile.tenant_id
                queryset = queryset.filter(tenant_id=tenant_id)
            except Exception:
                queryset = queryset.none()

        return queryset
