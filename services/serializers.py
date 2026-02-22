from rest_framework import serializers
from .models import ServiceType, RodieService


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ('id', 'name', 'code', 'category', 'fixed_price', 'image', 'is_active', 'created_at', 'updated_at')


class RodieServiceSerializer(serializers.ModelSerializer):
    service = ServiceTypeSerializer(read_only=True)
    rodie_username = serializers.CharField(source='rodie.username', read_only=True)

    class Meta:
        model = RodieService
        fields = ('id', 'rodie', 'rodie_username', 'service', 'created_at', 'updated_at')
