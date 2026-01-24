from rest_framework import serializers
from .models import ServiceRequest
from services.admin_serializers import ServiceTypeSerializer
from django.contrib.auth import get_user_model
from .models import charge_fee_for_request
from decimal import Decimal
from django.utils import timezone

try:
    from services.models import ServiceType
except ImportError:
    ServiceType = None

User = get_user_model()


class ServiceRequestAdminSerializer(serializers.ModelSerializer):
    rider_username = serializers.CharField(source='rider.username', read_only=True)
    rodie_username = serializers.CharField(source='rodie.username', read_only=True)
    rider_username_input = serializers.CharField(write_only=True, required=False)
    rodie_username_input = serializers.CharField(write_only=True, required=False)
    service_type_name = serializers.CharField(source='service_type.name', read_only=True)
    
    if ServiceType:
        service_type_id = serializers.PrimaryKeyRelatedField(
            queryset=ServiceType.objects.all(), 
            source='service_type', 
            write_only=True,
            required=False
        )
    
    service_type_details = ServiceTypeSerializer(source='service_type', read_only=True)

    class Meta:
        model = ServiceRequest
        fields = (
            'id', 'rider', 'rider_username', 'rodie', 'rodie_username',
            'service_type', 'service_type_name', 'service_type_details',
            'status', 'rider_lat', 'rider_lng',
            'is_paid', 'fee_charged',
            'accepted_at', 'en_route_at', 'started_at', 'completed_at',
            'created_at', 'updated_at',
            'rider_username_input', 'rodie_username_input'
        )

        if ServiceType:
            fields += ('service_type_id',)

    def validate(self, attrs):
        rider_username = self.initial_data.get('rider_username') or self.initial_data.get('rider_username_input')
        if rider_username and not attrs.get('rider'):
            try:
                attrs['rider'] = User.objects.get(username=rider_username, role='RIDER')
            except User.DoesNotExist:
                raise serializers.ValidationError({'rider_username': 'Rider user not found'})

        rodie_username = self.initial_data.get('rodie_username') or self.initial_data.get('rodie_username_input')
        if rodie_username and not attrs.get('rodie'):
            try:
                attrs['rodie'] = User.objects.get(username=rodie_username, role='RODIE')
            except User.DoesNotExist:
                raise serializers.ValidationError({'rodie_username': 'Rodie user not found'})
        
        if not attrs.get('rider'):
            raise serializers.ValidationError({'rider': 'This field is required.'})

        try:
            from users.models import Wallet, PlatformConfig
            cfg = PlatformConfig.objects.first()
            max_neg = cfg.max_negative_balance if cfg else Decimal('0')
            rider = attrs.get('rider') or getattr(self.instance, 'rider', None)
            if rider:
                rider_wallet, _ = Wallet.objects.get_or_create(user=rider)
                if rider_wallet.balance < Decimal(-max_neg):
                    raise serializers.ValidationError({'rider': 'Rider wallet below allowed negative balance; cannot create request.'})
            rodie = attrs.get('rodie') or getattr(self.instance, 'rodie', None)
            if rodie:
                rodie_wallet, _ = Wallet.objects.get_or_create(user=rodie)
                if rodie_wallet.balance < Decimal(-max_neg):
                    raise serializers.ValidationError({'rodie': 'Rodie wallet below allowed negative balance; cannot assign request.'})
        except serializers.ValidationError:
            raise
        except Exception:
            pass

        return attrs

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        new_status = validated_data.get('status', instance.status)
        new_rodie = validated_data.get('rodie', instance.rodie)

        if new_status == 'ACCEPTED':
            if not new_rodie:
                raise serializers.ValidationError({'rodie': 'A rodie must be assigned to accept the request.'})
            if not getattr(new_rodie, 'is_approved', False):
                raise serializers.ValidationError({'rodie': 'Rodie is not approved to accept requests.'})


        updated = super().update(instance, validated_data)

        try:
            if updated.status == 'ACCEPTED' and not updated.accepted_at:
                updated.accepted_at = timezone.now()
                updated.save(update_fields=['accepted_at'])
            if updated.status == 'EN_ROUTE' and not updated.en_route_at:
                updated.en_route_at = timezone.now()
                updated.save(update_fields=['en_route_at'])
            if updated.status == 'STARTED' and not updated.started_at:
                updated.started_at = timezone.now()
                updated.save(update_fields=['started_at'])
            if updated.status == 'COMPLETED' and not updated.completed_at:
                updated.completed_at = timezone.now()
                updated.save(update_fields=['completed_at'])
        except Exception:
            pass
        try:
            if updated.status == 'COMPLETED' and updated.is_paid and not updated.fee_charged:
                charge_fee_for_request(updated)

            if 'fee_charged' in self.initial_data and self.initial_data.get('fee_charged') and not getattr(instance, 'fee_charged', False):
                charge_fee_for_request(updated)
        except Exception:
            pass

        return updated