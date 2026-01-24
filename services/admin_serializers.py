from rest_framework import serializers
from .models import ServiceType, RodieService
from django.contrib.auth import get_user_model

User = get_user_model()


class ServiceTypeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, allow_blank=False)
    code = serializers.CharField(required=True, allow_blank=False)
    rodie_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ServiceType
        fields = ('id', 'name', 'code', 'fixed_price', 'image', 'is_active', 'created_at', 'updated_at', 'rodie_count')
        read_only_fields = ('created_at', 'updated_at')

    def validate(self, attrs):
        return attrs

    def get_rodie_count(self, obj):
        try:
            return RodieService.objects.filter(service=obj).count()
        except Exception:
            return 0


class RodieServiceSerializer(serializers.ModelSerializer):
    rodie_username = serializers.CharField(source='rodie.username', read_only=True)
    service_display = serializers.CharField(source='service.name', read_only=True)

    rodie_username_input = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = RodieService
        fields = ('id', 'rodie', 'rodie_username', 'rodie_username_input', 'service', 'service_display', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

    def validate(self, attrs):
        rodie_username = self.initial_data.get('rodie_username') or self.initial_data.get('rodie_username_input')
        if rodie_username and not attrs.get('rodie'):
            try:
                attrs['rodie'] = User.objects.get(username=rodie_username)
            except User.DoesNotExist:
                raise serializers.ValidationError({'rodie_username': 'Rodie user not found'})
        rodie = attrs.get('rodie')
        if rodie and getattr(rodie, 'role', None) != 'RODIE':
            raise serializers.ValidationError({'rodie': 'User is not a rodie'})
        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)
