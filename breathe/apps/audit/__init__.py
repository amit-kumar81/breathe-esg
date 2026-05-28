"""Audit logging app — append-only AuditLog written by Django signals on every model save/delete."""

default_app_config = 'breathe.apps.audit.apps.AuditConfig'
