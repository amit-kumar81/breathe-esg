"""Auth app config."""

from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'breathe.apps.auth'
    label = 'breathe_auth'
    verbose_name = 'Authentication & Multi-Tenancy'

    def ready(self):
        pass
