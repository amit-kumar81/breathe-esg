"""
Audit logging models for tracking all changes to ESG emissions data.

Chunk 1.6: Audit Logging (Every Change)

Design Philosophy:
- AuditLog: immutable, append-only record of every change
- Captures object_type, object_id, action (CREATE/UPDATE/DELETE)
- Stores old vs. new values in change_summary (JSON)
- Tenant-isolated for multi-tenancy compliance
- Can't be modified or deleted (raises error on update)
"""

import uuid
from django.db import models
from breathe.apps.tenants.models import Tenant


class AuditLog(models.Model):
    """
    Immutable audit log entry for tracking changes to data models.

    Created when:
    - EmissionsDataPoint is created, updated, or deleted
    - ReviewTask is created, updated, or deleted
    - NormalizedRecord is created, updated, or deleted

    Immutability:
    - Can only be created, never modified or deleted
    - Attempting to save an existing AuditLog raises ValidationError
    - Django signals trigger auto-creation on model changes

    Audit Trail:
    - Captures full before/after state in change_summary
    - Tracks who made the change (user_id) and when (timestamp)
    - Stores request IP address for forensic analysis
    - Tenant-isolated to prevent cross-tenant visibility
    """

    ACTION_CHOICES = (
        ('CREATE', 'Record created'),
        ('UPDATE', 'Record updated'),
        ('DELETE', 'Record deleted'),
    )

    # Primary key and identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # What changed
    object_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of object: EmissionsDataPoint, ReviewTask, NormalizedRecord"
    )
    object_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="UUID of the object being audited"
    )

    # Tenant isolation
    tenant_id = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        db_index=True
    )

    # Action and metadata
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)

    # What changed (for updates: old_values and new_values)
    # For creates: only new_values populated
    # For deletes: only old_values populated
    change_summary = models.JSONField(
        default=dict,
        help_text="JSON: {'old_values': {...}, 'new_values': {...}}"
    )

    # Who made the change
    user_id = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="User who triggered the change (null=system action)"
    )

    # When and where
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.CharField(
        max_length=45,
        blank=True,
        null=True,
        help_text="IPv4 (15 chars) or IPv6 (45 chars)"
    )

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
        """
        Override save to enforce append-only constraint.

        Raises:
            ValueError: If trying to update an existing AuditLog (immutable)
        """
        if self.pk and self.id:
            # Trying to update an existing AuditLog
            raise ValueError(
                "AuditLog entries are immutable and cannot be modified. "
                "Create a new entry instead."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Override delete to prevent removal of audit logs.

        Raises:
            ValueError: AuditLog entries cannot be deleted
        """
        raise ValueError(
            "AuditLog entries are immutable and cannot be deleted. "
            "This is a compliance requirement for audit trail integrity."
        )
