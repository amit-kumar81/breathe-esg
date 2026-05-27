"""
ViewSets for analyst review workflow API endpoints.

Chunk 2.2: Analyst Review Workflow API

Endpoints:
- GET /api/review/pending/ → list tasks awaiting review
- POST /api/review/{task_id}/approve/ → analyst approves
- POST /api/review/{task_id}/reject/ → analyst rejects
- POST /api/review/{task_id}/request_clarification/ → request changes
- POST /api/review/batch_approve/ → batch operation
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter
from django.utils import timezone
from django.db import transaction

from breathe.apps.review.models import ReviewTask, ReviewApproval
from breathe.apps.review.serializers import (
    ReviewTaskListSerializer,
    ReviewTaskDetailSerializer,
    ApprovalActionSerializer,
    BatchApprovalSerializer
)
from breathe.apps.audit.models import AuditLog
from breathe.apps.emissions.models import EmissionsDataPoint


class ReviewTaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for analyst review workflow.
    
    List endpoint:
        GET /api/review/pending/
        Returns all pending ReviewTasks
    
    Detail endpoint:
        GET /api/review/{id}/
        Returns full ReviewTask with validation errors
    
    Custom actions:
        POST /api/review/{id}/approve/
        POST /api/review/{id}/reject/
        POST /api/review/{id}/request_clarification/
        POST /api/review/batch_approve/
    """
    
    queryset = ReviewTask.objects.all()
    filter_backends = [OrderingFilter]
    ordering_fields = ['priority', 'created_at']
    ordering = ['-priority', '-created_at']

    def get_queryset(self):
        qs = ReviewTask.objects.all()
        status = self.request.query_params.get('status')
        priority = self.request.query_params.get('priority')
        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        return qs
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ReviewTaskDetailSerializer
        return ReviewTaskListSerializer
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """GET /api/review/pending/ - List pending tasks"""
        pending_tasks = ReviewTask.objects.filter(
            status='PENDING'
        ).order_by('-priority', '-created_at')
        
        page = self.paginate_queryset(pending_tasks)
        if page is not None:
            serializer = ReviewTaskListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ReviewTaskListSerializer(pending_tasks, many=True)
        return Response({'count': pending_tasks.count(), 'results': serializer.data})
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """POST /api/review/{id}/approve/ - Approve record"""
        review_task = self.get_object()
        serializer = ApprovalActionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            review_task.status = 'APPROVED'
            review_task.approved_by = request.user
            review_task.approved_at = timezone.now()
            review_task.analyst_notes = serializer.validated_data.get('notes', '')
            review_task.save()
            
            ReviewApproval.objects.create(
                review_task_id=review_task,
                tenant_id=review_task.tenant_id,
                analyst=request.user,
                decision='APPROVED',
                notes=serializer.validated_data.get('notes', '')
            )
            
            if review_task.normalized_record_id:
                emissions, created = EmissionsDataPoint.objects.get_or_create(
                    normalized_record_id=review_task.normalized_record_id,
                    defaults={
                        'tenant_id': review_task.tenant_id,
                        'normalized_values': review_task.normalized_record_id.normalized_values,
                        'validation_errors': review_task.normalized_record_id.validation_errors,
                        'data_quality_flags': review_task.normalized_record_id.data_quality_flags,
                        'is_valid': review_task.normalized_record_id.is_valid,
                        'data_quality_score': review_task.normalized_record_id.data_quality_score,
                        'review_status': 'APPROVED',
                        'reviewed_at': timezone.now()
                    }
                )
                
                AuditLog.objects.create(
                    object_type='EmissionsDataPoint',
                    object_id=str(emissions.id),
                    tenant_id=review_task.tenant_id,
                    action='UPDATE' if not created else 'CREATE',
                    change_summary={'review_status': 'APPROVED'},
                    user_id=request.user,
                    ip_address=self._get_client_ip(request)
                )
        
        return Response({'status': 'approved', 'message': 'Record approved'})
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """POST /api/review/{id}/reject/ - Reject record"""
        review_task = self.get_object()
        serializer = ApprovalActionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            review_task.status = 'REJECTED'
            review_task.rejected_by = request.user
            review_task.rejected_at = timezone.now()
            review_task.rejection_reason = serializer.validated_data.get('notes', '')
            review_task.save()
            
            ReviewApproval.objects.create(
                review_task_id=review_task,
                tenant_id=review_task.tenant_id,
                analyst=request.user,
                decision='REJECTED',
                notes=serializer.validated_data.get('notes', '')
            )
        
        return Response({'status': 'rejected', 'message': 'Record rejected'})
    
    @action(detail=True, methods=['post'])
    def request_clarification(self, request, pk=None):
        """POST /api/review/{id}/request_clarification/ - Request changes"""
        review_task = self.get_object()
        serializer = ApprovalActionSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            review_task.status = 'PENDING_CHANGES'
            review_task.analyst_notes = serializer.validated_data.get('notes', '')
            review_task.save()
            
            ReviewApproval.objects.create(
                review_task_id=review_task,
                tenant_id=review_task.tenant_id,
                analyst=request.user,
                decision='FLAG_FOR_EXPERT',
                notes=serializer.validated_data.get('notes', '')
            )
        
        return Response({'status': 'pending_changes', 'message': 'Changes requested'})
    
    @action(detail=False, methods=['post'])
    def batch_approve(self, request):
        """POST /api/review/batch_approve/ - Batch approve/reject"""
        serializer = BatchApprovalSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        task_ids = serializer.validated_data['task_ids']
        decision = serializer.validated_data['decision']
        notes = serializer.validated_data.get('notes', '')
        
        approved_count = 0
        
        with transaction.atomic():
            for task_id in task_ids:
                try:
                    task = ReviewTask.objects.get(id=task_id)
                    task.status = 'APPROVED' if decision == 'APPROVED' else 'REJECTED'
                    if decision == 'APPROVED':
                        task.approved_by = request.user
                        task.approved_at = timezone.now()
                    else:
                        task.rejected_by = request.user
                        task.rejected_at = timezone.now()
                    task.analyst_notes = notes
                    task.save()
                    
                    ReviewApproval.objects.create(
                        review_task_id=task,
                        tenant_id=task.tenant_id,
                        analyst=request.user,
                        decision=decision,
                        notes=notes
                    )
                    
                    approved_count += 1
                except ReviewTask.DoesNotExist:
                    pass
        
        return Response({'status': 'completed', 'approved_count': approved_count})
    
    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', '')
