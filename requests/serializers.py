from rest_framework import serializers
from .models import ServiceRequest
from services.models import ServiceType
try:
    from .models_chat import ChatMessage
except Exception:
    ChatMessage = None


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)

    class Meta:
        model = ChatMessage
        fields = ('id', 'service_request', 'sender_id', 'text', 'created_at')
        read_only_fields = ('created_at', 'sender_id')


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

    class Meta:
        model = ServiceRequest
        fields = ('id', 'service_type', 'service_type_name', 'rider_id', 'rodie_id', 'status', 'rider_lat', 'rider_lng', 'accepted_at', 'en_route_at', 'started_at', 'completed_at', 'is_paid', 'fee_charged', 'created_at', 'updated_at')
        read_only_fields = ('accepted_at', 'en_route_at', 'started_at', 'completed_at', 'created_at', 'updated_at')
