"""
Chunk 2.3: Multi-Tenancy Isolation - Auth App Config
"""

from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'breathe.apps.auth'
    label = 'breathe_auth'
    verbose_name = 'Authentication & Multi-Tenancy'

    def ready(self):
        # Import signals if needed
        pass
