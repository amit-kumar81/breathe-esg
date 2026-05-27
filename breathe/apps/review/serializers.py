from rest_framework import serializers
from breathe.apps.review.models import ReviewTask, ReviewApproval


class ReviewApprovalSerializer(serializers.ModelSerializer):
    analyst_name = serializers.CharField(source='analyst.username', read_only=True, allow_null=True)

    class Meta:
        model = ReviewApproval
        fields = ['id', 'decision', 'analyst_name', 'notes', 'created_at']
        read_only_fields = fields


class ReviewTaskListSerializer(serializers.ModelSerializer):
    """Flat serializer for the list view — reads direct NormalizedRecord fields."""

    facility_name      = serializers.CharField(source='normalized_record_id.facility_name',      read_only=True, allow_null=True)
    scope_1_emissions  = serializers.FloatField(source='normalized_record_id.scope_1_emissions',  read_only=True, allow_null=True)
    scope_2_emissions  = serializers.FloatField(source='normalized_record_id.scope_2_emissions',  read_only=True, allow_null=True)
    scope_3_emissions  = serializers.FloatField(source='normalized_record_id.scope_3_emissions',  read_only=True, allow_null=True)
    reporting_year     = serializers.IntegerField(source='normalized_record_id.reporting_year',   read_only=True, allow_null=True)
    data_quality_score = serializers.IntegerField(source='normalized_record_id.data_quality_score', read_only=True, allow_null=True)
    validation_errors  = serializers.JSONField(source='normalized_record_id.validation_errors',   read_only=True, allow_null=True)
    error_count        = serializers.SerializerMethodField()

    class Meta:
        model = ReviewTask
        fields = [
            'id', 'status', 'priority', 'reason_codes',
            'facility_name', 'reporting_year',
            'scope_1_emissions', 'scope_2_emissions', 'scope_3_emissions',
            'data_quality_score', 'validation_errors', 'error_count',
            'analyst_notes', 'approved_at', 'rejected_at', 'created_at',
        ]
        read_only_fields = fields

    def get_error_count(self, obj):
        if obj.normalized_record_id and isinstance(obj.normalized_record_id.validation_errors, list):
            return len(obj.normalized_record_id.validation_errors)
        return 0


class ReviewTaskDetailSerializer(ReviewTaskListSerializer):
    """Extends list serializer with decision history."""

    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True, allow_null=True)
    rejected_by_name = serializers.CharField(source='rejected_by.username', read_only=True, allow_null=True)
    decision_history = serializers.SerializerMethodField()

    class Meta(ReviewTaskListSerializer.Meta):
        fields = ReviewTaskListSerializer.Meta.fields + [
            'rejection_reason',
            'approved_by_name', 'rejected_by_name',
            'decision_history',
        ]

    def get_decision_history(self, obj):
        approvals = ReviewApproval.objects.filter(review_task_id=obj.id).order_by('-created_at')
        return ReviewApprovalSerializer(approvals, many=True).data


class ApprovalActionSerializer(serializers.Serializer):
    """Used by approve/reject endpoints — decision is implied by the URL so it's optional here."""
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class BatchApprovalSerializer(serializers.Serializer):
    task_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=100)
    decision = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    notes    = serializers.CharField(max_length=1000, required=False, allow_blank=True)
