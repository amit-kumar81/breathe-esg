"""
Minimal Django Admin for Tenants. No over-engineering.
"""

from django.contrib import admin
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'plan', 'is_active', 'created_at')
    list_filter = ('plan', 'is_active', 'created_at')
    search_fields = ('name', 'slug')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fields = ('name', 'slug', 'description', 'plan', 'is_active', 'id', 'created_at', 'updated_at')
