"""Django admin for user profiles."""

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
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            try:
                tenant_id = request.user.profile.tenant_id
                queryset = queryset.filter(tenant_id=tenant_id)
            except Exception:
                queryset = queryset.none()

        return queryset
