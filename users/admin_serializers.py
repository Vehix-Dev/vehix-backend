from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class AdminPaymentSerializer(serializers.ModelSerializer):
    """Serializer for viewing payment/withdrawal requests in admin panel."""
    user_details = serializers.SerializerMethodField()

    class Meta:
        model = None  # Set dynamically in __init__ to avoid circular imports
        fields = (
            'id', 'user', 'user_details', 'amount', 'transaction_type', 
            'status', 'reference', 'processor_id', 'description',
            'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'user', 'amount', 'transaction_type', 'reference',
            'processor_id', 'created_at', 'updated_at'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set model dynamically to avoid circular import issues
        if self.Meta.model is None:
            try:
                from .models import Payment
                self.Meta.model = Payment
            except Exception:
                pass

    def get_user_details(self, obj):
        """Include user details in the payment response."""
        return {
            'id': obj.user.id,
            'external_id': obj.user.external_id,
            'username': obj.user.username,
            'email': obj.user.email,
            'phone': obj.user.phone,
            'role': obj.user.role,
        }


class AdminWithdrawalApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting withdrawal requests."""
    status = serializers.ChoiceField(
        choices=['COMPLETED', 'FAILED', 'CANCELLED'],
        required=True,
        help_text="Set to COMPLETED to approve, FAILED or CANCELLED to reject."
    )
    rejection_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional reason for rejection (when status is FAILED or CANCELLED)."
    )

    def validate(self, data):
        status = data.get('status')
        # If approving, no additional validation needed
        # If rejecting, rejection_reason is optional but recommended
        return data


class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    wallet = None
    is_online = serializers.BooleanField(read_only=True)
    device_type = serializers.SerializerMethodField()
    profile_photo = serializers.SerializerMethodField()
    id_card_front = serializers.SerializerMethodField()
    id_card_back = serializers.SerializerMethodField()
    license_photo = serializers.SerializerMethodField()
    vehicle_photo = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()

    try:
        from .serializers import WalletSerializer
        wallet = WalletSerializer(read_only=True)
    except Exception:
        wallet = None

    class Meta:
        model = User
        fields = (
            'id', 'external_id', 'first_name', 'last_name', 'email', 'phone', 
            'username', 'password', 'role', 'referral_code', 'nin', 
            'is_approved', 'is_online', 'device_type', 'created_at', 'updated_at', 'wallet',
            'is_active', 'is_deleted',
            'profile_photo', 'id_card_front', 
            'id_card_back', 'license_photo', 'vehicle_photo',
            'rating', 'rating_count',
        )
        read_only_fields = ('external_id', 'referral_code', 'created_at', 'updated_at')
        extra_kwargs = {
            'role': {'required': False},
            'email': {'required': False},
            'phone': {'required': False},
            'is_approved': {'required': False},
        }

    def _get_user_image(self, obj, image_type):
        from images.models import UserImage
        image = UserImage.objects.filter(user=obj, image_type=image_type).order_by('-created_at').first()
        if image and image.original_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image.original_image.url)
            return image.original_image.url
        return None

    def get_device_type(self, obj):
        try:
            from .models import RodieAvailabilityLog
            log = (
                RodieAvailabilityLog.objects.filter(user=obj)
                .order_by('-went_online_at')
                .first()
            )
            if log and log.device_type:
                return log.device_type
        except Exception:
            pass
        return None

    def get_profile_photo(self, obj):
        return self._get_user_image(obj, 'PROFILE')

    def get_id_card_front(self, obj):
        return self._get_user_image(obj, 'NIN_FRONT') or self._get_user_image(obj, 'ID_CARD_FRONT')

    def get_id_card_back(self, obj):
        return self._get_user_image(obj, 'NIN_BACK') or self._get_user_image(obj, 'ID_CARD_BACK')

    def get_license_photo(self, obj):
        return self._get_user_image(obj, 'LICENSE')

    def get_vehicle_photo(self, obj):
        return self._get_user_image(obj, 'VEHICLE')

    def get_rating(self, obj):
        try:
            from service_requests.models_rating import Rating
            from django.db.models import Avg
            avg = Rating.objects.filter(rated_user=obj).aggregate(avg=Avg('rating'))['avg']
            return round(float(avg), 1) if avg is not None else 5.0
        except Exception:
            return 5.0

    def get_rating_count(self, obj):
        try:
            from service_requests.models_rating import Rating
            return Rating.objects.filter(rated_user=obj).count()
        except Exception:
            return 0


    def create(self, validated_data):
        password = validated_data.pop('password', None)
        role = validated_data.get('role')
        
        # Enforce default password for Riders and Roadies created via Admin API
        if role in ('RIDER', 'RODIE'):
            password = '2026'
            # Generate username from phone if not provided
            if not validated_data.get('username') and validated_data.get('phone'):
                validated_data['username'] = validated_data['phone']

        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        if validated_data.get('role') == 'RIDER':
            user.is_approved = True
            user.is_active = True
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def validate(self, data):
        role = data.get('role')
        nin = data.get('nin')
        if role in ('RIDER', 'RODIE'):
            # NIN is optional during creation, but if provided, it must be valid
            if nin:
                if len(nin) != 14:
                    raise serializers.ValidationError({'nin': 'NIN must be exactly 14 characters'})
                if User.objects.filter(nin=nin).exists():
                    raise serializers.ValidationError({'nin': 'This NIN is already in use'})
        return data


class AdminCreateSerializer(AdminUserSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta(AdminUserSerializer.Meta):
        pass

    def create(self, validated_data):
        validated_data['role'] = 'ADMIN'
        validated_data['is_staff'] = True
        validated_data['is_superuser'] = True
        validated_data['is_approved'] = True
        username = validated_data.get('username')
        if username:
            validated_data['username'] = username.strip()

        validated_data['is_active'] = True

        return super(AdminCreateSerializer, self).create(validated_data)
