from rest_framework import serializers
from breathe.apps.ingest.models import NormalizedRecord


class NormalizedRecordReviewSerializer(serializers.ModelSerializer):
    """
    Serializes a NormalizedRecord for the analyst review queue.

    NormalizedRecord is the single source of truth — review_status lives here,
    not in a separate ReviewTask table. This serializer exposes the fields the
    review UI needs, plus backward-compatible aliases (status, approved_by_name,
    rejected_by_name) so the frontend needs no changes.
    """
    # Expose review_status as 'status' for frontend compatibility
    status = serializers.CharField(source='review_status', read_only=True)
    priority = serializers.CharField(read_only=True)  # computed property on model
    reviewed_by_name = serializers.CharField(source='reviewed_by.username', read_only=True, allow_null=True)

    # Frontend uses approved_by_name / rejected_by_name — derive from review_status
    approved_by_name = serializers.SerializerMethodField()
    rejected_by_name = serializers.SerializerMethodField()

    scope_1_emissions = serializers.FloatField(allow_null=True)
    scope_2_emissions = serializers.FloatField(allow_null=True)
    scope_3_emissions = serializers.FloatField(allow_null=True)

    class Meta:
        model = NormalizedRecord
        fields = [
            'id', 'status', 'priority',
            'facility_name', 'reporting_year',
            'scope_1_emissions', 'scope_2_emissions', 'scope_3_emissions',
            'data_quality_score', 'validation_errors',
            'reviewed_at', 'reviewed_by_name',
            'approved_by_name', 'rejected_by_name',
            'created_at',
        ]
        read_only_fields = fields

    def get_approved_by_name(self, obj):
        if obj.review_status == 'APPROVED' and obj.reviewed_by:
            return obj.reviewed_by.username
        return None

    def get_rejected_by_name(self, obj):
        if obj.review_status == 'REJECTED' and obj.reviewed_by:
            return obj.reviewed_by.username
        return None


class ApprovalActionSerializer(serializers.Serializer):
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
