"""
Chunk 2.4: Ingestion Workflow Endpoints - URLs

Routes for ingestion workflow:
- POST /api/ingest/upload/ - Upload CSV
- POST /api/ingest/{id}/parse/ - Parse CSV into rows
- POST /api/ingest/{id}/normalize/ - Normalize and validate
- GET /api/ingest/{id}/status/ - Check progress
- GET /api/ingest/{id}/ - Full details
- GET /api/ingest/ - List ingestions
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_workflow import IngestionViewSet

router = DefaultRouter()
router.register(r'', IngestionViewSet, basename='ingestion')

app_name = 'ingest'

urlpatterns = [
    path('', include(router.urls)),
]
