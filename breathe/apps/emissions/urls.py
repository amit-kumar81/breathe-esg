"""URL routing for emissions API endpoints."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from breathe.apps.emissions.views import EmissionsDataPointViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r'', EmissionsDataPointViewSet, basename='emissions')

# URL patterns
urlpatterns = [
    path('', include(router.urls)),
]

