"""
Serializers for ReviewTask and analyst review workflow.

Chunk 2.2: Analyst Review Workflow API

Design Philosophy:
- ReviewTask serializer shows what needs review
- Approval action serializer handles approve/reject/clarification
- Include related EmissionsDataPoint and validation errors
"""

from rest_framework import serializers
from breathe.apps.review.models import ReviewTask, ReviewApproval
from breathe.apps.emissions.models import EmissionsDataPoint


class ReviewApprovalSerializer(serializers.ModelSerializer):
    """
    Serializes ReviewApproval (immutable audit log of decisions).
    """
    analyst_name = serializers.CharField(source='analyst.username', read_only=True, allow_null=True)
    
    class Meta:
        model = ReviewApproval
        fields = [
            'id',
            'decision',
            'analyst_name',
            'notes',
            'created_at'
        ]
        read_only_fields = fields


class ReviewTaskListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing ReviewTasks.
    Shows what needs review without full details.
    """
    # Flattened emissions data
    facility_name = serializers.CharField(
        source='normalized_record_id.normalized_values.facility_name',
        read_only=True,
        allow_null=True
    )
    scope_1_emissions = serializers.FloatField(
        source='normalized_record_id.normalized_values.scope_1_emissions',
        read_only=True,
        allow_null=True
    )
    year = serializers.IntegerField(
        source='normalized_record_id.normalized_values.year',
        read_only=True,
        allow_null=True
    )
    
    # Count of issues
    error_count = serializers.SerializerMethodField()
    flag_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ReviewTask
        fields = [
            'id',
            'facility_name',
            'scope_1_emissions',
            'year',
            'status',
            'priority',
            'error_count',
            'flag_count',
            'analyst_notes',
            'created_at'
        ]
        read_only_fields = fields
    
    def get_error_count(self, obj):
        """Count validation errors."""
        if obj.normalized_record_id and obj.normalized_record_id.validation_errors:
            if isinstance(obj.normalized_record_id.validation_errors, list):
                return len(obj.normalized_record_id.validation_errors)
        return 0
    
    def get_flag_count(self, obj):
        """Count data quality flags."""
        if obj.normalized_record_id and obj.normalized_record_id.data_quality_flags:
            if isinstance(obj.normalized_record_id.data_quality_flags, list):
                return len(obj.normalized_record_id.data_quality_flags)
        return 0


class ReviewTaskDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for ReviewTask.
    Includes full record details, validation errors, and decision history.
    """
    # Flattened emissions data
    facility_name = serializers.CharField(
        source='normalized_record_id.normalized_values.facility_name',
        read_only=True,
        allow_null=True
    )
    scope_1_emissions = serializers.FloatField(
        source='normalized_record_id.normalized_values.scope_1_emissions',
        read_only=True,
        allow_null=True
    )
    scope_2_emissions = serializers.FloatField(
        source='normalized_record_id.normalized_values.scope_2_emissions',
        read_only=True,
        allow_null=True
    )
    scope_3_emissions = serializers.FloatField(
        source='normalized_record_id.normalized_values.scope_3_emissions',
        read_only=True,
        allow_null=True
    )
    year = serializers.IntegerField(
        source='normalized_record_id.normalized_values.year',
        read_only=True,
        allow_null=True
    )
    
    # Full validation details
    validation_errors = serializers.JSONField(
        source='normalized_record_id.validation_errors',
        read_only=True
    )
    data_quality_flags = serializers.JSONField(
        source='normalized_record_id.data_quality_flags',
        read_only=True
    )
    data_quality_score = serializers.IntegerField(
        source='normalized_record_id.data_quality_score',
        read_only=True
    )
    
    # Analyst info
    approved_by_name = serializers.CharField(
        source='approved_by.username',
        read_only=True,
        allow_null=True
    )
    rejected_by_name = serializers.CharField(
        source='rejected_by.username',
        read_only=True,
        allow_null=True
    )
    
    # Decision history (approvals on this task)
    decision_history = serializers.SerializerMethodField()
    
    class Meta:
        model = ReviewTask
        fields = [
            'id',
            'facility_name',
            'scope_1_emissions',
            'scope_2_emissions',
            'scope_3_emissions',
            'year',
            'validation_errors',
            'data_quality_flags',
            'data_quality_score',
            'status',
            'priority',
            'reason_codes',
            'analyst_notes',
            'approved_by_name',
            'approved_at',
            'rejected_by_name',
            'rejected_at',
            'rejection_reason',
            'decision_history',
            'created_at'
        ]
        read_only_fields = [f for f in fields if f != 'analyst_notes']
    
    def get_decision_history(self, obj):
        """Get all ReviewApproval entries for this task."""
        approvals = ReviewApproval.objects.filter(
            review_task_id=obj.id
        ).order_by('-created_at')
        return ReviewApprovalSerializer(approvals, many=True).data


class ApprovalActionSerializer(serializers.Serializer):
    """
    Serializer for approve/reject/clarification actions.
    Validates the request and returns response.
    """
    decision = serializers.ChoiceField(
        choices=['APPROVED', 'REJECTED', 'PENDING_CHANGES'],
        help_text="Decision: APPROVED, REJECTED, or PENDING_CHANGES"
    )
    notes = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="Analyst feedback or reason for rejection"
    )
    
    def validate_notes(self, value):
        """Ensure notes are provided for rejections."""
        decision = self.initial_data.get('decision')
        if decision in ['REJECTED', 'PENDING_CHANGES'] and not value:
            raise serializers.ValidationError(
                "Notes are required when rejecting or requesting changes"
            )
        return value


class BatchApprovalSerializer(serializers.Serializer):
    """
    Serializer for batch approval operations.
    Approve/reject multiple tasks at once.
    """
    task_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text="List of ReviewTask IDs to approve/reject"
    )
    decision = serializers.ChoiceField(
        choices=['APPROVED', 'REJECTED'],
        help_text="Decision to apply to all tasks"
    )
    notes = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="Notes for batch operation"
    )
    
    def validate_task_ids(self, value):
        """Ensure at least 1 task ID."""
        if len(value) == 0:
            raise serializers.ValidationError("At least 1 task ID required")
        if len(value) > 100:
            raise serializers.ValidationError("Maximum 100 tasks per batch")
        return value

