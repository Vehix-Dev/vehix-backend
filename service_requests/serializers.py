from django.core.cache import cache
from locations.utils import calculate_distance_km
from rest_framework import serializers
from .models import ServiceRequest, CancellationReason, RequestCancellation
from services.models import ServiceType
try:
    from .models_chat import ChatMessage
except Exception:
    ChatMessage = None

try:
    from .models_rating import Rating
except Exception:
    Rating = None


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    sender_role = serializers.SerializerMethodField()
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ('id', 'service_request', 'sender_id', 'sender_role', 'sender_name', 'text', 'is_read', 'created_at')
        read_only_fields = ('created_at', 'sender_id', 'is_read')

    def get_sender_role(self, obj):
        if obj.sender_id == obj.service_request.rider_id:
            return 'RIDER'
        if obj.service_request.rodie_id and obj.sender_id == obj.service_request.rodie_id:
            return 'RODIE'
        return 'UNKNOWN'

    def get_sender_name(self, obj):
        return obj.sender.username


class ServiceRequestCreateSerializer(serializers.ModelSerializer):
    service_type_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ServiceRequest
        fields = ('id', 'service_type', 'service_type_name', 'rider_lat', 'rider_lng')

    def create(self, validated_data):
        if not validated_data.get('service_type'):
            raw = self.initial_data.get('service_type') or self.initial_data.get('service_type_name') or self.initial_data.get('service_name')
            if raw:
                st = None
                try:
                    if str(raw).isdigit():
                        st = ServiceType.objects.filter(id=int(raw)).first()
                except Exception:
                    st = None
                if not st:
                    st = ServiceType.objects.filter(name__iexact=raw).first() or ServiceType.objects.filter(code__iexact=raw).first()
                if not st:
                    raise serializers.ValidationError({'service_type': f"Service type '{raw}' not found"})
                validated_data['service_type'] = st
        return super().create(validated_data)


class ServiceRequestSerializer(serializers.ModelSerializer):
    rider_id = serializers.IntegerField(source='rider.id', read_only=True)
    rodie_id = serializers.IntegerField(source='rodie.id', read_only=True)
    service_type_name = serializers.CharField(source='service_type.name', read_only=True)
    rider_phone = serializers.CharField(source='rider.phone', read_only=True)
    rodie_phone = serializers.CharField(source='rodie.phone', read_only=True)
    rider_name = serializers.SerializerMethodField()
    rodie_name = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()
    eta_seconds = serializers.SerializerMethodField()

    rider_username = serializers.ReadOnlyField(source='rider.username')
    rodie_username = serializers.ReadOnlyField(source='rodie.username')

    class Meta:
        model = ServiceRequest
        fields = (
            'id', 'service_type', 'service_type_name', 'rider_id', 'rodie_id', 
            'rider_name', 'rodie_name', 'rider_username', 'rodie_username', 
            'rider_phone', 'rodie_phone',
            'status', 'rider_lat', 'rider_lng', 'accepted_at', 'en_route_at', 
            'started_at', 'completed_at', 'is_paid', 'fee_charged', 'created_at', 'updated_at',
            'distance_km', 'eta_seconds'
        )
        read_only_fields = ('accepted_at', 'en_route_at', 'started_at', 'completed_at', 'created_at', 'updated_at')

    def get_rider_name(self, obj):
        if obj.rider:
            return obj.rider.username
        return None

    def get_rodie_name(self, obj):
        if obj.rodie:
            return obj.rodie.username
        return None

    def get_distance_km(self, obj):
        if obj.rodie_id and obj.rider_lat and obj.rider_lng:
            loc = cache.get(f"rodie_loc:{obj.rodie_id}")
            if loc:
                try:
                    return calculate_distance_km(
                        float(loc['lat']), float(loc['lng']),
                        float(obj.rider_lat), float(obj.rider_lng)
                    )
                except Exception:
                    return None
        return None

    def get_eta_seconds(self, obj):
        dist = self.get_distance_km(obj)
        if dist is not None:
            # Estimate 30 km/h
            return int((dist / 30) * 3600)
        return None


class RatingSerializer(serializers.ModelSerializer):
    rater_username = serializers.CharField(source='rater.username', read_only=True)
    rated_user_username = serializers.CharField(source='rated_user.username', read_only=True)
    service_request_id = serializers.IntegerField(source='service_request.id', read_only=True)
    
    class Meta:
        model = Rating
        fields = (
            'id', 'service_request', 'service_request_id', 'rater', 'rater_username',
            'rated_user', 'rated_user_username', 'rating', 'comment',
            'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at')
        ref_name = 'ServiceRatingSerializer'


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


class RatingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ('service_request', 'rating', 'comment')
    
    def validate(self, data):
        request = self.context['request']
        service_request = data.get('service_request')
        user = request.user
        
        # Verify user is either roadie or rider for this request
        if user.id != service_request.rider_id and user.id != (service_request.rodie_id or 0):
            raise serializers.ValidationError("You are not part of this service request.")
        
        # Only completed requests can be rated
        if service_request.status != 'COMPLETED':
            raise serializers.ValidationError("You can only rate a completed service.")
                
        # Check if already rated by this user
        if Rating.objects.filter(service_request=service_request, rater=user).exists():
            raise serializers.ValidationError("You have already rated this service request.")
            
        return data
        
    def create(self, validated_data):
        request = self.context['request']
        validated_data['rater'] = request.user
        return super().create(validated_data)
