"""
Review workflow models (ReviewTask, ReviewApproval).
These are kept for DB compatibility; the active review flow now uses NormalizedRecord.review_status.
"""

import uuid
from django.db import models
from breathe.apps.tenants.models import Tenant
from breathe.apps.ingest.models import NormalizedRecord


class ReviewTask(models.Model):
    """Legacy review task model. Kept for existing data; not created by current pipeline."""
    STATUS_CHOICES = (
        ('PENDING', 'Awaiting review'),
        ('APPROVED', 'Approved by analyst'),
        ('REJECTED', 'Rejected by analyst'),
        ('PENDING_CHANGES', 'Awaiting re-submission'),
    )

    PRIORITY_CHOICES = (
        ('LOW', 'Low priority'),
        ('MEDIUM', 'Medium priority'),
        ('HIGH', 'High priority (missing critical data)'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ingestion_id = models.ForeignKey(
        'ingest.RawIngestion',
        on_delete=models.CASCADE,
        related_name='review_tasks'
    )
    normalized_record_id = models.ForeignKey(
        NormalizedRecord,
        on_delete=models.CASCADE,
        related_name='review_task',
        null=True,
        blank=True
    )
    tenant_id = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='review_tasks')

    # Status and priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')

    # Reason why this record needs review
    reason_codes = models.JSONField(
        default=list,
        help_text="Codes explaining why review is needed: ['validation_error', 'low_quality', 'auto_flag']"
    )

    # Analyst notes and decision
    analyst_notes = models.TextField(blank=True, null=True, help_text="Notes from analyst during review")

    # Approval metadata
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_review_tasks'
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Rejection metadata
    rejected_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_review_tasks'
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True, help_text="Why was this rejected?")

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'review_review_task'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant_id']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['ingestion_id']),
        ]

    def __str__(self):
        return f"Review Task {self.id}: {self.status} (Priority: {self.priority})"


class ReviewApproval(models.Model):
    """
    Record of analyst's approval decision.

    Immutable audit log: once created, never modified.
    Tracks:
    - Who approved/rejected
    - When
    - Decision (approve/reject)
    - Reason/notes
    """
    DECISION_CHOICES = (
        ('APPROVED', 'Approved for analytics'),
        ('REJECTED', 'Rejected, request re-submission'),
        ('FLAG_FOR_EXPERT', 'Flag for expert review'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review_task_id = models.ForeignKey(
        ReviewTask,
        on_delete=models.CASCADE,
        related_name='approvals'
    )
    tenant_id = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='review_approvals')

    # Approval details
    analyst = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    notes = models.TextField(blank=True, null=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'review_review_approval'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant_id']),
            models.Index(fields=['decision']),
        ]

    def __str__(self):
        return f"Approval: {self.decision} by {self.analyst} at {self.created_at}"
