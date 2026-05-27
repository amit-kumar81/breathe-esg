"""
Django AppConfig for audit logging app.

Chunk 1.6: Audit Logging (Every Change)

Registers signal handlers on app ready to ensure
audit logging is enabled throughout the application lifecycle.
"""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'breathe.apps.audit'
    verbose_name = 'Audit Logs'

    def ready(self):
        """
        Import signal handlers when app is ready.
        This ensures Django signals are registered before any model operations.
        """
        import breathe.apps.audit.signals  # noqa: F401
