"""Audit app config — registers signal handlers on startup."""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'breathe.apps.audit'
    verbose_name = 'Audit Logs'

    def ready(self):
        import breathe.apps.audit.signals  # noqa: F401
