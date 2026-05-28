"""
Signal handlers that write an AuditLog entry on every model save/delete.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from threading import local
import uuid
from decimal import Decimal

from breathe.apps.audit.models import AuditLog
from breathe.apps.emissions.models import EmissionsDataPoint
from breathe.apps.review.models import ReviewTask
from breathe.apps.ingest.models import NormalizedRecord


# Thread-local storage for request context (user, IP, tenant_id)
_thread_locals = local()


def get_audit_context():
    return {
        'user': getattr(_thread_locals, 'user', None),
        'ip_address': getattr(_thread_locals, 'ip_address', None),
        'tenant_id': getattr(_thread_locals, 'tenant_id', None),
    }


def set_audit_context(user=None, ip_address=None, tenant_id=None):
    _thread_locals.user = user
    _thread_locals.ip_address = ip_address
    _thread_locals.tenant_id = tenant_id


def get_changed_fields(instance, old_instance=None):
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
        if value is None or isinstance(value, (bool, int, float, str, dict, list)):
            pass
        elif hasattr(value, 'isoformat'):
            value = value.isoformat()
        elif isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, Decimal):
            value = float(value)
        else:
            value = str(value)
        
        data[field.name] = value
    
    return data


@receiver(post_save, sender=EmissionsDataPoint)
def log_emissions_data_point_change(sender, instance, created, **kwargs):
    context = get_audit_context()
    
    if not context['tenant_id']:
        # Try to get tenant_id from instance if not in context
        if hasattr(instance, 'tenant_id'):
            context['tenant_id'] = instance.tenant_id
    
    if created:
        action = 'CREATE'
        change_summary = {'new_values': _serialize_instance(instance)}
    else:
        action = 'UPDATE'
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
