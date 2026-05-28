from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction

from breathe.apps.ingest.models import NormalizedRecord
from breathe.apps.review.serializers import NormalizedRecordReviewSerializer, ApprovalActionSerializer
from breathe.apps.auth.permissions import IsAnalyst


class ReviewTaskViewSet(viewsets.ViewSet):
    permission_classes = [IsAnalyst]

    def _get_paginated(self, request, queryset):
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = NormalizedRecordReviewSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = NormalizedRecordReviewSerializer(queryset, many=True)
        return Response({'count': queryset.count(), 'results': serializer.data})

    def list(self, request):
        """GET /api/review/?status=PENDING_REVIEW|APPROVED|REJECTED"""
        status_param = request.query_params.get('status', 'PENDING_REVIEW')

        # Accept legacy 'PENDING' from the frontend
        if status_param == 'PENDING':
            status_param = 'PENDING_REVIEW'

        qs = NormalizedRecord.objects.filter(review_status=status_param).select_related('reviewed_by')
        return self._get_paginated(request, qs)

    def retrieve(self, request, pk=None):
        """GET /api/review/{id}/"""
        try:
            nr = NormalizedRecord.objects.select_related('reviewed_by').get(id=pk)
        except NormalizedRecord.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(NormalizedRecordReviewSerializer(nr).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """POST /api/review/{id}/approve/"""
        try:
            nr = NormalizedRecord.objects.get(id=pk)
        except NormalizedRecord.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ApprovalActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            nr.review_status = 'APPROVED'
            nr.reviewed_by = request.user
            nr.reviewed_at = timezone.now()
            nr.reviewer_notes = serializer.validated_data.get('notes', '')
            nr.save(update_fields=['review_status', 'reviewed_by', 'reviewed_at', 'reviewer_notes'])

        return Response({'status': 'approved', 'message': 'Record approved'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """POST /api/review/{id}/reject/"""
        try:
            nr = NormalizedRecord.objects.get(id=pk)
        except NormalizedRecord.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ApprovalActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            nr.review_status = 'REJECTED'
            nr.reviewed_by = request.user
            nr.reviewed_at = timezone.now()
            nr.reviewer_notes = serializer.validated_data.get('notes', '')
            nr.save(update_fields=['review_status', 'reviewed_by', 'reviewed_at', 'reviewer_notes'])

        return Response({'status': 'rejected', 'message': 'Record rejected'})
