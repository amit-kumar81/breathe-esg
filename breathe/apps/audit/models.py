"""
Audit logging: immutable, append-only record of every model change.
"""

import uuid
from django.db import models
from breathe.apps.tenants.models import Tenant


class AuditLog(models.Model):
    """Immutable audit log entry. Created by signals on model save/delete; cannot be modified or deleted."""

    ACTION_CHOICES = (
        ('CREATE', 'Record created'),
        ('UPDATE', 'Record updated'),
        ('DELETE', 'Record deleted'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    object_type = models.CharField(max_length=50, db_index=True)
    object_id = models.CharField(max_length=50, db_index=True)
    tenant_id = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='audit_logs', db_index=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)
    change_summary = models.JSONField(default=dict)
    user_id = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)

    class Meta:
        db_table = 'audit_audit_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant_id']),
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['action']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['user_id']),
        ]

    def __str__(self):
        return f"Audit {self.action} {self.object_type}({self.object_id}) at {self.timestamp}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("AuditLog entries are immutable and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog entries cannot be deleted.")
