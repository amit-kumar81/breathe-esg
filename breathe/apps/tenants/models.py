"""
Tenant model for multi-tenancy.
"""

import uuid
from django.db import models


class Tenant(models.Model):
    """
    Represents a company using the platform.
    """
    PLAN_CHOICES = [
        ('FREE', 'Free'),
        ('STARTER', 'Starter'),
        ('PROFESSIONAL', 'Professional'),
        ('ENTERPRISE', 'Enterprise'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Company name")
    slug = models.SlugField(max_length=100, unique=True, help_text="URL-friendly identifier")
    description = models.TextField(blank=True, null=True)
    plan = models.CharField(max_length=50, choices=PLAN_CHOICES, default='STARTER')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenants_tenant'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return f"{self.name} ({self.slug})"
