"""
Ingest URLs.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import IngestionViewSet

router = DefaultRouter()
router.register(r'', IngestionViewSet, basename='ingestion')

urlpatterns = [
    path('', include(router.urls)),
]
