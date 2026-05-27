"""
Django signal handlers for automatic audit logging.

Chunk 1.6: Audit Logging (Every Change)

Design Philosophy:
- Use Django post_save and post_delete signals to trigger logging
- Capture old vs. new values by querying database before update
- Extract user from request context (thread-local storage or signal kwargs)
- Create AuditLog entries automatically on model changes
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from threading import local

from breathe.apps.audit.models import AuditLog
from breathe.apps.emissions.models import EmissionsDataPoint
from breathe.apps.review.models import ReviewTask
from breathe.apps.ingest.models import NormalizedRecord


# Thread-local storage for request context (user, IP, tenant_id)
_thread_locals = local()


def get_audit_context():
    """
    Retrieve audit context (user, ip_address, tenant_id) from thread-local storage.
    
    Returns:
        dict: {'user': User|None, 'ip_address': str|None, 'tenant_id': Tenant|None}
    """
    return {
        'user': getattr(_thread_locals, 'user', None),
        'ip_address': getattr(_thread_locals, 'ip_address', None),
        'tenant_id': getattr(_thread_locals, 'tenant_id', None),
    }


def set_audit_context(user=None, ip_address=None, tenant_id=None):
    """
    Set audit context in thread-local storage.
    Typically called from middleware on each request.
    
    Args:
        user: Django User object or None
        ip_address: IP address string or None
        tenant_id: Tenant object or None
    """
    _thread_locals.user = user
    _thread_locals.ip_address = ip_address
    _thread_locals.tenant_id = tenant_id


def get_changed_fields(instance, old_instance=None):
    """
    Capture what changed between old_instance and instance.
    
    Args:
        instance: Current model instance
        old_instance: Previous model instance (if available)
    
    Returns:
        dict: {'old_values': {...}, 'new_values': {...}}
    """
    if old_instance is None:
        # No old instance means this is a CREATE
        return {
            'new_values': _serialize_instance(instance)
        }
    
    # Compare old vs. new values
    old_dict = _serialize_instance(old_instance)
    new_dict = _serialize_instance(instance)
    
    return {
        'old_values': old_dict,
        'new_values': new_dict
    }


def _serialize_instance(instance):
    """
    Convert model instance to serializable dict (excluding relations).
    
    Args:
        instance: Django model instance
    
    Returns:
        dict: Serializable representation of instance fields
    """
    data = {}
    for field in instance._meta.fields:
        # Skip relations (FK, M2M)
        if field.many_to_one or field.many_to_many or field.one_to_one:
            # For FK fields, store the ID instead of object
            if field.many_to_one:
                value = getattr(instance, f"{field.name}_id", None)
            else:
                value = None
        else:
            value = getattr(instance, field.name, None)
        
        # Convert non-JSON-serializable types
        if hasattr(value, 'isoformat'):  # datetime, date, time
            value = value.isoformat()
        elif hasattr(value, '__dict__') and not isinstance(value, dict):
            value = str(value)
        
        data[field.name] = value
    
    return data


# ============================================================================
# Signal Handlers for Each Model
# ============================================================================

@receiver(post_save, sender=EmissionsDataPoint)
def log_emissions_data_point_change(sender, instance, created, **kwargs):
    """
    Auto-log when EmissionsDataPoint is created or updated.
    """
    context = get_audit_context()
    
    if not context['tenant_id']:
        # Try to get tenant_id from instance if not in context
        if hasattr(instance, 'tenant_id'):
            context['tenant_id'] = instance.tenant_id
    
    if created:
        action = 'CREATE'
        change_summary = {
            'new_values': _serialize_instance(instance)
        }
    else:
        action = 'UPDATE'
        # Get old instance from database (before this signal)
        try:
            old_instance = EmissionsDataPoint.objects.get(pk=instance.pk)
            change_summary = get_changed_fields(instance, old_instance)
        except EmissionsDataPoint.DoesNotExist:
            change_summary = {'new_values': _serialize_instance(instance)}
    
    AuditLog.objects.create(
        object_type='EmissionsDataPoint',
        object_id=str(instance.id),
        tenant_id=context['tenant_id'],
        action=action,
        change_summary=change_summary,
        user_id=context['user'],
        ip_address=context['ip_address']
    )


@receiver(post_save, sender=ReviewTask)
def log_review_task_change(sender, instance, created, **kwargs):
    """
    Auto-log when ReviewTask is created or updated.
    """
    context = get_audit_context()
    
    if not context['tenant_id']:
        if hasattr(instance, 'tenant_id'):
            context['tenant_id'] = instance.tenant_id
    
    if created:
        action = 'CREATE'
        change_summary = {
            'new_values': _serialize_instance(instance)
        }
    else:
        action = 'UPDATE'
        try:
            old_instance = ReviewTask.objects.get(pk=instance.pk)
            change_summary = get_changed_fields(instance, old_instance)
        except ReviewTask.DoesNotExist:
            change_summary = {'new_values': _serialize_instance(instance)}
    
    AuditLog.objects.create(
        object_type='ReviewTask',
        object_id=str(instance.id),
        tenant_id=context['tenant_id'],
        action=action,
        change_summary=change_summary,
        user_id=context['user'],
        ip_address=context['ip_address']
    )


@receiver(post_save, sender=NormalizedRecord)
def log_normalized_record_change(sender, instance, created, **kwargs):
    """
    Auto-log when NormalizedRecord is created or updated.
    """
    context = get_audit_context()
    
    if not context['tenant_id']:
        if hasattr(instance, 'tenant_id'):
            context['tenant_id'] = instance.tenant_id
    
    if created:
        action = 'CREATE'
        change_summary = {
            'new_values': _serialize_instance(instance)
        }
    else:
        action = 'UPDATE'
        try:
            old_instance = NormalizedRecord.objects.get(pk=instance.pk)
            change_summary = get_changed_fields(instance, old_instance)
        except NormalizedRecord.DoesNotExist:
            change_summary = {'new_values': _serialize_instance(instance)}
    
    AuditLog.objects.create(
        object_type='NormalizedRecord',
        object_id=str(instance.id),
        tenant_id=context['tenant_id'],
        action=action,
        change_summary=change_summary,
        user_id=context['user'],
        ip_address=context['ip_address']
    )


@receiver(post_delete, sender=EmissionsDataPoint)
def log_emissions_data_point_delete(sender, instance, **kwargs):
    """
    Auto-log when EmissionsDataPoint is deleted.
    Note: post_delete receives instance AFTER deletion, so we can still access it.
    """
    context = get_audit_context()
    
    if not context['tenant_id']:
        if hasattr(instance, 'tenant_id'):
            context['tenant_id'] = instance.tenant_id
    
    AuditLog.objects.create(
        object_type='EmissionsDataPoint',
        object_id=str(instance.id),
        tenant_id=context['tenant_id'],
        action='DELETE',
        change_summary={
            'old_values': _serialize_instance(instance)
        },
        user_id=context['user'],
        ip_address=context['ip_address']
    )


@receiver(post_delete, sender=ReviewTask)
def log_review_task_delete(sender, instance, **kwargs):
    """
    Auto-log when ReviewTask is deleted.
    """
    context = get_audit_context()
    
    if not context['tenant_id']:
        if hasattr(instance, 'tenant_id'):
            context['tenant_id'] = instance.tenant_id
    
    AuditLog.objects.create(
        object_type='ReviewTask',
        object_id=str(instance.id),
        tenant_id=context['tenant_id'],
        action='DELETE',
        change_summary={
            'old_values': _serialize_instance(instance)
        },
        user_id=context['user'],
        ip_address=context['ip_address']
    )


@receiver(post_delete, sender=NormalizedRecord)
def log_normalized_record_delete(sender, instance, **kwargs):
    """
    Auto-log when NormalizedRecord is deleted.
    """
    context = get_audit_context()
    
    if not context['tenant_id']:
        if hasattr(instance, 'tenant_id'):
            context['tenant_id'] = instance.tenant_id
    
    AuditLog.objects.create(
        object_type='NormalizedRecord',
        object_id=str(instance.id),
        tenant_id=context['tenant_id'],
        action='DELETE',
        change_summary={
            'old_values': _serialize_instance(instance)
        },
        user_id=context['user'],
        ip_address=context['ip_address']
    )
