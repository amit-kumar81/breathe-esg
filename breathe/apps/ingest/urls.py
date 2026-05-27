"""
Ingest URLs.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import IngestionViewSet, DataSourceListView

router = DefaultRouter()
router.register(r'', IngestionViewSet, basename='ingestion')

urlpatterns = [
    path('datasources/', DataSourceListView.as_view(), name='datasource-list'),
    path('', include(router.urls)),
]
