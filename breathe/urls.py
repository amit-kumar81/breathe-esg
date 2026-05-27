"""
URL configuration for breathe project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint for monitoring and deployment platforms."""
    return JsonResponse({
        "status": "ok",
        "version": "1.0.0",
        "service": "breathe-esg"
    })

urlpatterns = [
    path('health/', health_check),
    path('admin/', admin.site.urls),
    path('api/', include([
        path('auth/', include('breathe.apps.auth.urls')),
        path('tenants/', include('breathe.apps.tenants.urls')),
        path('ingest/', include('breathe.apps.ingest.urls')),
        path('emissions/', include('breathe.apps.emissions.urls')),
        path('review/', include('breathe.apps.review.urls')),
        path('audit/', include('breathe.apps.audit.urls')),
    ])),
]
