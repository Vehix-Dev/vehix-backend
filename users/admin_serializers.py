from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    wallet = None
    try:
        from .serializers import WalletSerializer
        wallet = WalletSerializer(read_only=True)
    except Exception:
        wallet = None

    class Meta:
        model = User
        fields = (
            'id', 'external_id', 'first_name', 'last_name', 'email', 'phone', 'username', 'password', 'role', 'referral_code', 'nin', 'is_approved', 'created_at', 'updated_at', 'wallet', 'is_active', 'is_deleted',
        )
        read_only_fields = ('external_id', 'referral_code', 'created_at', 'updated_at')
        extra_kwargs = {
            'role': {'required': False},
            'email': {'required': False},
            'phone': {'required': False},
            'is_approved': {'required': False},
        }

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
