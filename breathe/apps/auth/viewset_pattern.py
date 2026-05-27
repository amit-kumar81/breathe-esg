"""
Chunk 2.3: Multi-Tenancy Isolation - ViewSet Integration Pattern

This file shows how to update existing ViewSets to support multi-tenancy.

All data-bearing ViewSets should:
1. Inherit from TenantQuerySetMixin
2. Add TenantIsolationPermission to permission_classes
3. Optionally add role-based permissions (IsAnalyst, IsDataProvider, etc.)

This ensures all QuerySets are filtered by tenant_id automatically.
"""

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from breathe.apps.auth.permissions import (
    TenantIsolationPermission,
    TenantQuerySetMixin,
    IsAnalyst
)
from breathe.apps.emissions.models import EmissionsDataPoint
from breathe.apps.emissions.serializers import (
    EmissionsDataPointListSerializer,
    EmissionsDataPointDetailSerializer
)
from breathe.apps.review.models import ReviewTask
from breathe.apps.review.serializers import (
    ReviewTaskListSerializer,
    ReviewTaskDetailSerializer
)


# ============================================================================
# BEFORE (OLD PATTERN - NO MULTI-TENANCY)
# ============================================================================

class OldEmissionsDataPointViewSet(viewsets.ReadOnlyModelViewSet):
    """Without multi-tenancy, any user can see any tenant's data"""
    queryset = EmissionsDataPoint.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return EmissionsDataPointListSerializer
        return EmissionsDataPointDetailSerializer

    # ❌ PROBLEM: No tenant isolation
    # - User A can see User B's data by guessing IDs
    # - No filtering on QuerySet


# ============================================================================
# AFTER (NEW PATTERN - WITH MULTI-TENANCY)
# ============================================================================

class EmissionsDataPointViewSet(TenantQuerySetMixin, viewsets.ReadOnlyModelViewSet):
    """
    With multi-tenancy, each user sees only their tenant's data.

    Key changes:
    1. Inherit from TenantQuerySetMixin
    2. Add TenantIsolationPermission
    3. get_queryset() is automatically scoped to user's tenant
    """
    queryset = EmissionsDataPoint.objects.all()
    permission_classes = [
        permissions.IsAuthenticated,
        TenantIsolationPermission
    ]

    def get_serializer_class(self):
        if self.action == 'list':
            return EmissionsDataPointListSerializer
        return EmissionsDataPointDetailSerializer

    # ✅ FIXED:
    # - User A can only see their tenant's data
    # - TenantQuerySetMixin filters QuerySet automatically
    # - TenantIsolationPermission checks object-level access


class ReviewTaskViewSet(TenantQuerySetMixin, viewsets.ModelViewSet):
    """
    Review endpoint with analyst-only approval.

    Pattern:
    1. TenantQuerySetMixin: Auto-filter by tenant
    2. TenantIsolationPermission: Check object ownership
    3. IsAnalyst: Only analysts can approve/reject
    """
    queryset = ReviewTask.objects.all()
    permission_classes = [
        permissions.IsAuthenticated,
        TenantIsolationPermission,
        IsAnalyst  # ← Only analysts can use this endpoint
    ]

    def get_serializer_class(self):
        if self.action == 'list':
            return ReviewTaskListSerializer
        return ReviewTaskDetailSerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """List pending tasks for this user's tenant"""
        # get_queryset() is already filtered by tenant
        queryset = self.get_queryset().filter(status='PENDING')
        serializer = ReviewTaskListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve a review task.

        Permissions checked:
        1. User is authenticated
        2. User's tenant owns this ReviewTask
        3. User is an analyst
        """
        review_task = self.get_object()

        # If we got here, all permission checks passed
        # (has_object_permission already validated tenant ownership)

        # Approval logic
        from breathe.apps.review.models import ReviewApproval
        from django.db import transaction

        with transaction.atomic():
            review_task.status = 'APPROVED'
            review_task.save()

            ReviewApproval.objects.create(
                review_task=review_task,
                analyst=request.user,
                decision='APPROVED',
                notes=request.data.get('notes', '')
            )

        return Response(
            {'status': 'approved'},
            status=status.HTTP_200_OK
        )


# ============================================================================
# SETTINGS & URLS CONFIGURATION
# ============================================================================

"""
In your settings.py:

INSTALLED_APPS = [
    ...
    'breathe.apps.auth',
    'breathe.apps.emissions',
    'breathe.apps.review',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}
"""

"""
In your main urls.py:

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from breathe.apps.auth.urls import urlpatterns as auth_urls
from breathe.apps.emissions.views import EmissionsDataPointViewSet
from breathe.apps.review.views import ReviewTaskViewSet

router = DefaultRouter()
router.register(r'emissions', EmissionsDataPointViewSet)
router.register(r'review', ReviewTaskViewSet)

urlpatterns = [
    path('api/auth/', include(auth_urls)),
    path('api/', include(router.urls)),
]
"""


# ============================================================================
# COMPLETE EXAMPLE: LOGIN → ACCESS API
# ============================================================================

"""
Frontend flow:

1. User logs in:
   POST /api/auth/login/
   {
     "username": "alice",
     "password": "password"
   }

   Response:
   {
     "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
     "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
     "user": {
       "username": "alice",
       "tenant": {
         "id": "tenant-abc",
         "name": "Acme Corp"
       },
       "role": "ANALYST"
     }
   }

2. Frontend stores access token, sends in all requests:
   GET /api/emissions/
   Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...

3. ViewSet processes request:
   a. JWTAuthentication validates token → request.user set
   b. IsAuthenticated checks request.user is not None
   c. TenantIsolationPermission checks request.user.profile.tenant_id
   d. TenantQuerySetMixin filters by tenant_id automatically
   e. Response includes only this tenant's data

4. User A cannot access User B's data:
   GET /api/emissions/{user_b_record_id}/

   Returns 403 Forbidden because:
   - TenantIsolationPermission.has_object_permission() checks
   - obj.tenant_id != request.user.profile.tenant_id

5. When token expires (15 min):
   POST /api/auth/refresh/
   {
     "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
   }

   Response:
   {
     "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
   }

   Frontend updates stored token, continues
"""
