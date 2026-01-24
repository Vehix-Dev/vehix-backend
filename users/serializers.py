from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal

from .models import Wallet, WalletTransaction, Referral, PlatformConfig, Notification, Payment
from services.models import RodieService

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    referred_by_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            'id',
            'first_name',
            'last_name',
            'email',
            'phone',
            'username',
            'password',
            'role',
            'nin',
            'referred_by_code',
        )

    def create(self, validated_data):
        code = validated_data.pop('referred_by_code', None)

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone=validated_data.get('phone'),
            role=validated_data.get('role'),
                nin=validated_data.get('nin'),
        )

        wallet, _ = Wallet.objects.get_or_create(user=user)

        if code:
            try:
                referrer = User.objects.filter(referral_code=code).first()
                if referrer and referrer != user:
                    ref_wallet, _ = Wallet.objects.get_or_create(user=referrer)
                    amount = Decimal('100.00')
                    ref_wallet.balance = ref_wallet.balance + amount
                    ref_wallet.save()
                    WalletTransaction.objects.create(wallet=ref_wallet, amount=amount, reason='referral credit')
                    Referral.objects.create(referrer=referrer, referred=user, amount=amount)
            except Exception:
                pass

        return user

    def validate(self, data):
        role = data.get('role')
        nin = data.get('nin')

        if role in ('RIDER', 'RODIE'):
            if not nin:
                raise serializers.ValidationError({'nin': 'NIN is required for riders and roadies'})
            if len(nin) != 14:
                raise serializers.ValidationError({'nin': 'NIN must be exactly 14 characters'})
            if User.objects.filter(nin=nin).exists():
                raise serializers.ValidationError({'nin': 'This NIN is already in use'})

        return data


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = ('id', 'amount', 'reason', 'created_at')


class WalletSerializer(serializers.ModelSerializer):
    transactions = WalletTransactionSerializer(many=True, read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_external_id = serializers.CharField(source='user.external_id', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Wallet
        fields = ('id', 'user_id', 'user_external_id', 'user_username', 'balance', 'transactions')


class NotificationSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    broadcast = serializers.BooleanField(required=False)
    target_role = serializers.ChoiceField(choices=(('RIDER', 'Rider'), ('RODIE', 'Rodie')), required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Notification
        fields = ('id', 'user', 'title', 'body', 'data', 'read', 'broadcast', 'target_role', 'created_at')
        read_only_fields = ('created_at',)

    def validate(self, attrs):
        user = attrs.get('user') if 'user' in attrs else None
        broadcast = attrs.get('broadcast') if 'broadcast' in attrs else False
        target_role = attrs.get('target_role') if 'target_role' in attrs else None

        if not user and not broadcast and not target_role:
            raise serializers.ValidationError('Notification must target a user, a role, or be broadcast')
        return attrs


class UserSerializer(serializers.ModelSerializer):
    wallet = WalletSerializer(read_only=True)
    services = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'external_id',
            'first_name',
            'last_name',
            'email',
            'phone',
            'username',
            'role',
            'referral_code',
            'nin',
            'is_approved',
            'created_at',
            'updated_at',
            'wallet',
            'services',
        )
        read_only_fields = ('external_id', 'referral_code', 'created_at', 'updated_at')

    def get_services(self, obj):
        if getattr(obj, 'role', None) != 'RODIE':
            return []
        qs = RodieService.objects.filter(rodie=obj).select_related('service')
        return [
            {
                'service_id': r.service.id, 
                'service_name': r.service.name,
                'fixed_price': r.service.fixed_price,
                'image': self.context['request'].build_absolute_uri(r.service.image.url) if r.service.image and 'request' in self.context else (r.service.image.url if r.service.image else None)
            } for r in qs
        ]



class ReferralSerializer(serializers.ModelSerializer):
    referrer = UserSerializer(read_only=True)
    referred = UserSerializer(read_only=True)

    class Meta:
        model = Referral
        fields = ('id', 'referrer', 'referred', 'amount', 'created_at')


class PlatformConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformConfig
        fields = ('id', 'max_negative_balance', 'service_fee', 'trial_days', 'updated_at')


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ('id', 'amount', 'transaction_type', 'status', 'reference', 'created_at')
        read_only_fields = ('id', 'status', 'reference', 'created_at')


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('1.00'))


class WithdrawSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('1.00'))
    phone_number = serializers.CharField(max_length=20, required=False)
    
    def validate_amount(self, value):
        # Balance check will be done in the view
        return value
