"""
Django admin configuration for audit logs.

Chunk 1.6: Audit Logging (Every Change)

Design Philosophy:
- Read-only admin interface (audit logs are immutable)
- Powerful filtering and search for forensic analysis
- Display change_summary as formatted JSON
- Tenant filtering for multi-tenancy compliance
"""

from django.contrib import admin
from django.utils.html import format_html
import json

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Read-only admin interface for AuditLog.
    
    Features:
    - View all audit entries (immutable)
    - Filter by object type, action, tenant, date range
    - Search by object_id or user
    - Pretty-print JSON change_summary
    - No edit/delete capabilities
    """

    # Display settings
    list_display = (
        'timestamp_display',
        'action_badge',
        'object_type',
        'object_id_short',
        'user_display',
        'tenant_id_display',
    )
    list_filter = (
        'action',
        'object_type',
        'tenant_id',
        'timestamp',
    )
    search_fields = ('object_id', 'user_id__username')
    readonly_fields = (
        'id',
        'object_type',
        'object_id',
        'tenant_id',
        'action',
        'change_summary_formatted',
        'user_id',
        'timestamp',
        'ip_address',
    )

    # Detail view
    fieldsets = (
        ('Identification', {
            'fields': ('id', 'object_type', 'object_id', 'tenant_id'),
        }),
        ('Action', {
            'fields': ('action', 'timestamp'),
        }),
        ('Changes', {
            'fields': ('change_summary_formatted',),
            'classes': ('wide',),
        }),
        ('Context', {
            'fields': ('user_id', 'ip_address'),
        }),
    )

    # Disable add/edit/delete
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # Custom display methods
    def timestamp_display(self, obj):
        """Display timestamp in human-readable format."""
        return obj.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
    timestamp_display.short_description = 'When'

    def action_badge(self, obj):
        """Display action as colored badge."""
        colors = {
            'CREATE': '#28a745',   # green
            'UPDATE': '#ffc107',   # yellow
            'DELETE': '#dc3545',   # red
        }
        color = colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="background-color:{}; color:white; padding:3px 8px; '
            'border-radius:3px; font-weight:bold;">{}</span>',
            color,
            obj.action
        )
    action_badge.short_description = 'Action'

    def object_id_short(self, obj):
        """Display shortened object_id (first 8 chars)."""
        return f"{obj.object_id[:8]}..."
    object_id_short.short_description = 'Object ID'

    def user_display(self, obj):
        """Display user who made the change."""
        if obj.user_id:
            return f"{obj.user_id.username} ({obj.user_id.email})"
        return "(system)"
    user_display.short_description = 'User'

    def tenant_id_display(self, obj):
        """Display tenant name."""
        if obj.tenant_id:
            return str(obj.tenant_id)
        return "(unknown)"
    tenant_id_display.short_description = 'Tenant'

    def change_summary_formatted(self, obj):
        """Display change_summary as formatted JSON."""
        if isinstance(obj.change_summary, dict):
            formatted = json.dumps(obj.change_summary, indent=2, default=str)
        else:
            formatted = str(obj.change_summary)
        
        return format_html(
            '<pre style="background-color:#f5f5f5; padding:10px; '
            'border-radius:3px; overflow-x:auto;">{}</pre>',
            formatted
        )
    change_summary_formatted.short_description = 'Changes'

    class Media:
        css = {
            'all': ('admin/css/audit.css',)
        }
