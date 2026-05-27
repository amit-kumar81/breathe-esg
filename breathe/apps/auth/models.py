from django.db import models
from django.contrib.auth.models import User
from breathe.apps.tenants.models import Tenant


class UserProfile(models.Model):
    """
    Extends Django's User with tenant association and role.
    One user belongs to exactly one tenant.
    """
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('ANALYST', 'Analyst'),
        ('DATA_PROVIDER', 'Data Provider'),
        ('VIEWER', 'Viewer'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='users')
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='ANALYST')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'user'], name='unique_user_per_tenant')
        ]

    def __str__(self):
        return f"{self.user.username} ({self.tenant.slug}) - {self.role}"

    @property
    def tenant_id(self):
        return self.tenant.id

    def has_permission(self, permission):
        if self.role == 'ADMIN':
            return True
        if permission == 'approve_records' and self.role == 'ANALYST':
            return True
        if permission == 'upload_data' and self.role in ['DATA_PROVIDER', 'ADMIN']:
            return True
        if permission == 'view_data' and self.role in ['ANALYST', 'VIEWER', 'ADMIN']:
            return True
        return False
