"""
Chunk 2.5: Data Export & Reporting - URLs

Export and reporting endpoints:
- GET /api/emissions/export/ - Download CSV/JSON
- GET /api/emissions/summary/ - Dashboard statistics
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_export import EmissionsExportViewSet

router = DefaultRouter()
router.register(r'', EmissionsExportViewSet, basename='emissions-export')

app_name = 'emissions-export'

urlpatterns = [
    path('', include(router.urls)),
]
