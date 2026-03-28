from django.core.cache import cache
from locations.utils import calculate_distance_km
from rest_framework import serializers
from .models import ServiceRequest
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
        name = f"{obj.sender.first_name} {obj.sender.last_name}".strip()
        return name or obj.sender.username


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

    class Meta:
        model = ServiceRequest
        fields = (
            'id', 'service_type', 'service_type_name', 'rider_id', 'rodie_id', 
            'rider_name', 'rodie_name', 'rider_phone', 'rodie_phone',
            'status', 'rider_lat', 'rider_lng', 'accepted_at', 'en_route_at', 
            'started_at', 'completed_at', 'is_paid', 'fee_charged', 'created_at', 'updated_at',
            'distance_km', 'eta_seconds'
        )
        read_only_fields = ('accepted_at', 'en_route_at', 'started_at', 'completed_at', 'created_at', 'updated_at')

    def get_rider_name(self, obj):
        if obj.rider:
            return f"{obj.rider.first_name} {obj.rider.last_name}".strip() or obj.rider.username
        return None

    def get_rodie_name(self, obj):
        if obj.rodie:
            return f"{obj.rodie.first_name} {obj.rodie.last_name}".strip() or obj.rodie.username
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
    rater_name = serializers.SerializerMethodField()
    rated_user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Rating
        fields = ('id', 'service_request', 'rater', 'rated_user', 'rating', 'comment', 
                  'rater_name', 'rated_user_name', 'created_at', 'updated_at')
        read_only_fields = ('rater', 'rated_user', 'created_at', 'updated_at')
    
    def get_rater_name(self, obj):
        if obj.rater:
            return f"{obj.rater.first_name} {obj.rater.last_name}".strip() or obj.rater.username
        return None

    def get_rated_user_name(self, obj):
        if obj.rated_user:
            return f"{obj.rated_user.first_name} {obj.rated_user.last_name}".strip() or obj.rated_user.username
        return None
