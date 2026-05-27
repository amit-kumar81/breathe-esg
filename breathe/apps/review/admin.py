"""
Minimal Django Admin for Review. No over-engineering.
"""

from django.contrib import admin
from .models import ReviewTask


@admin.register(ReviewTask)
class ReviewTaskAdmin(admin.ModelAdmin):
    list_display = ('normalized_record_id', 'status', 'approved_by', 'created_at', 'approved_at')
    list_filter = ('status', 'created_at')
    search_fields = ('normalized_record_id__id',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    fields = ('tenant_id', 'ingestion_id', 'normalized_record_id', 'status', 'priority', 'reason_codes', 'analyst_notes', 'approved_by', 'approved_at', 'rejected_by', 'rejected_at', 'rejection_reason', 'id', 'created_at')
