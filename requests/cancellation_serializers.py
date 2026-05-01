from rest_framework import serializers
from .models import RequestCancellation, CancellationReason


class CancellationReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = CancellationReason
        fields = ('id', 'role', 'reason', 'requires_custom_text', 'is_active', 'order')
        read_only_fields = ('id',)


class RequestCancellationSerializer(serializers.ModelSerializer):
    """Serializer for request cancellation details"""
    reason_text = serializers.CharField(source='reason.reason', read_only=True)
    cancelled_by_username = serializers.CharField(source='cancelled_by.username', read_only=True)
    cancelled_by_role = serializers.CharField(source='cancelled_by.role', read_only=True)
    request_id = serializers.IntegerField(source='request.id', read_only=True)
    display_reason = serializers.SerializerMethodField()
    
    class Meta:
        model = RequestCancellation
        fields = (
            'id', 'request_id', 'cancelled_by', 'cancelled_by_username', 'cancelled_by_role',
            'reason', 'reason_text', 'custom_reason_text', 'display_reason',
            'cancelled_at', 'distance_at_cancellation', 'time_to_arrival_at_cancellation'
        )
        read_only_fields = ('cancelled_at',)
    
    def get_display_reason(self, obj):
        """Return the full reason string for display"""
        if obj.reason:
            if obj.reason.requires_custom_text and obj.custom_reason_text:
                return f"{obj.reason.reason}: {obj.custom_reason_text}"
            return obj.reason.reason
        return obj.custom_reason_text or "No reason provided"
