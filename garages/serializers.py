from rest_framework import serializers
from .models import Garage, GarageServiceRequest
from django.contrib.auth import get_user_model

User = get_user_model()


class GarageRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for garage registration/onboarding"""
    owner_id_front = serializers.ImageField(required=False)
    owner_id_back = serializers.ImageField(required=False)
    business_registration_cert = serializers.FileField(required=False)
    trading_license = serializers.FileField(required=False)
    local_authority_letter = serializers.FileField(required=False)
    exterior_photo = serializers.ImageField(required=True)
    interior_workshop_photo = serializers.ImageField(required=True)
    tools_equipment_photo = serializers.ImageField(required=False)

    class Meta:
        model = Garage
        fields = [
            # Garage Identity
            'name', 'garage_type', 'years_in_operation', 'physical_address',
            'latitude', 'longitude', 'operating_hours', 'primary_phone',
            'secondary_phone', 'business_email',

            # Ownership & Management
            'owner_name', 'owner_national_id', 'owner_id_front', 'owner_id_back',
            'owner_phone', 'owner_email', 'emergency_contact_name', 'emergency_contact_phone',
            'manager_name', 'manager_phone', 'manager_email',

            # Legal & Business Documents
            'business_registration_cert', 'tin_tax_id', 'trading_license', 'local_authority_letter',

            # Workshop Proof
            'exterior_photo', 'interior_workshop_photo', 'tools_equipment_photo',

            # Services Offered
            'vehicle_types', 'services_offered', 'services_not_offered',

            # Pricing Information
            'pricing_info', 'is_price_negotiable',

            # Staff & Skills
            'mechanics_count', 'lead_mechanic_name', 'experience_years',
            'certifications', 'specialized_skills',

            # Service Policies
            'warranty_offered', 'warranty_duration_days', 'avg_turnaround_hours',
            'emergency_service_available', 'working_days', 'cancellation_policy',

            # Banking & Payments
            'payment_method', 'account_holder_name', 'account_number',
            'provider_name', 'settlement_preference',

            # Compliance & Agreements
            'terms_accepted',
        ]
        read_only_fields = ['application_tracking_id', 'verification_status', 'submission_completeness', 'registration_date']

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError("You must accept the Vehix partner terms to register.")
        return value

    def validate_vehicle_types(self, value):
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError("At least one vehicle type must be selected.")
        valid_types = [choice[0] for choice in Garage.VEHICLE_TYPES]
        for v_type in value:
            if v_type not in valid_types:
                raise serializers.ValidationError(f"Invalid vehicle type: {v_type}")
        return value

    def validate_services_offered(self, value):
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError("At least one service must be offered.")
        valid_services = [choice[0] for choice in Garage.SERVICE_CATEGORIES]
        for service in value:
            if service not in valid_services:
                raise serializers.ValidationError(f"Invalid service category: {service}")
        return value


class GarageListSerializer(serializers.ModelSerializer):
    """Serializer for listing garages (public view for riders)"""
    distance = serializers.SerializerMethodField()

    class Meta:
        model = Garage
        fields = [
            'id', 'name', 'garage_type', 'physical_address', 'latitude', 'longitude',
            'operating_hours', 'primary_phone', 'business_email', 'vehicle_types',
            'services_offered', 'pricing_info', 'is_price_negotiable', 'warranty_offered',
            'warranty_duration_days', 'avg_turnaround_hours', 'emergency_service_available',
            'working_days', 'distance'
        ]

    def get_distance(self, obj):
        # This would calculate distance from rider's location
        # For now, return None - implement with geolocation later
        return None


class GarageDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for garage profile view"""

    class Meta:
        model = Garage
        fields = [
            'id', 'name', 'garage_type', 'years_in_operation', 'physical_address',
            'latitude', 'longitude', 'operating_hours', 'primary_phone', 'secondary_phone',
            'business_email', 'vehicle_types', 'services_offered', 'services_not_offered',
            'pricing_info', 'is_price_negotiable', 'mechanics_count', 'lead_mechanic_name',
            'experience_years', 'certifications', 'specialized_skills', 'warranty_offered',
            'warranty_duration_days', 'avg_turnaround_hours', 'emergency_service_available',
            'working_days', 'cancellation_policy', 'verification_status'
        ]


class GarageServiceRequestSerializer(serializers.ModelSerializer):
    """Serializer for garage service requests from riders"""
    rider = serializers.PrimaryKeyRelatedField(read_only=True)
    garage_name = serializers.CharField(source='garage.name', read_only=True)
    rider_name = serializers.CharField(source='rider.username', read_only=True)

    class Meta:
        model = GarageServiceRequest
        fields = [
            'id', 'rider', 'rider_name', 'garage', 'garage_name', 'vehicle_type',
            'service_category', 'description', 'preferred_date', 'preferred_time',
            'location_lat', 'location_lng', 'status', 'estimated_cost', 'actual_cost',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'rider', 'status', 'estimated_cost', 'actual_cost', 'created_at', 'updated_at']

    def validate_preferred_date(self, value):
        from django.utils import timezone
        if value < timezone.now().date():
            raise serializers.ValidationError("Preferred date cannot be in the past.")
        return value


class GarageApplicationStatusSerializer(serializers.Serializer):
    """Serializer for checking garage application status by tracking ID"""
    application_tracking_id = serializers.CharField(max_length=10, required=True)

    def validate_application_tracking_id(self, value):
        try:
            garage = Garage.objects.get(application_tracking_id=value.upper())
            return value.upper()
        except Garage.DoesNotExist:
            raise serializers.ValidationError("Invalid application tracking ID.")


class GarageStatusResponseSerializer(serializers.ModelSerializer):
    """Serializer for garage application status response"""
    verified_by_name = serializers.CharField(source='verified_by.username', read_only=True)

    class Meta:
        model = Garage
        fields = [
            'application_tracking_id', 'name', 'verification_status', 'submission_completeness',
            'registration_date', 'verified_at', 'rejection_reason', 'suspension_reason',
            'verified_by_name'
        ]


class GarageAdminSerializer(serializers.ModelSerializer):
    """Admin serializer for managing garages"""
    verified_by_name = serializers.CharField(source='verified_by.username', read_only=True)

    class Meta:
        model = Garage
        fields = '__all__'
        read_only_fields = ['submission_completeness', 'registration_date', 'registration_ip', 'device_type']

    def update(self, instance, validated_data):
        # Handle verification status changes
        new_status = validated_data.get('verification_status')
        if new_status and new_status != instance.verification_status:
            if new_status in ['VERIFIED', 'REJECTED', 'SUSPENDED']:
                instance.verified_by = self.context['request'].user
                instance.verified_at = serializers.DateTimeField().to_representation(serializers.DateTimeField().get_default())
                if new_status == 'REJECTED':
                    instance.rejection_reason = validated_data.get('rejection_reason', '')
                elif new_status == 'SUSPENDED':
                    instance.suspension_reason = validated_data.get('suspension_reason', '')

        return super().update(instance, validated_data)
