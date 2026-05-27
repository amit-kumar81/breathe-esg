"""
Audit logging app for tracking all changes to ESG emissions data.

Chunk 1.6: Audit Logging (Every Change)

Design Philosophy:
- Every change to EmissionsDataPoint, ReviewTask, NormalizedRecord is logged
- Append-only audit trail (can't modify or delete audit logs)
- Captures old vs. new values for updates
- Tenant-isolated (analysts can only query their own tenant's logs)
- Uses Django signals for automatic logging on model save/delete
"""

default_app_config = 'breathe.apps.audit.apps.AuditConfig'
