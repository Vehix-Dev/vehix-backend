from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import get_user_model
from django.db import models

from .serializers import RegisterSerializer, UserSerializer
from .serializers import WalletSerializer, ReferralSerializer, PlatformConfigSerializer, NotificationSerializer, DepositSerializer, WithdrawSerializer, PaymentSerializer, TransactionHistorySerializer, RoadiePaymentSummarySerializer, UserProfileUpdateSerializer, UserProfilePhotoSerializer
from .models import Wallet, Referral, PlatformConfig, Notification, Payment, WalletTransaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
try:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
except Exception:
    async_to_sync = None
    get_channel_layer = None

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class UserProfileUpdateView(APIView):
    """
    Update authenticated user's profile information
    GET: Get user profile details
    PATCH: Update profile fields (name, email, phone, username)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get current user profile"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        """Update user profile"""
        serializer = UserProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Profile updated successfully',
                'user': UserSerializer(request.user).data
            }, status=status.HTTP_200_OK)
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class UserProfilePhotoUploadView(APIView):
    """
    Upload or update user's profile photo
    POST: Upload a new profile photo
    GET: Get profile photo URL
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        """Get user's profile photo"""
        from images.models import UserImage
        try:
            profile_image = UserImage.objects.filter(
                user=request.user,
                image_type='PROFILE'
            ).order_by('-created_at').first()
            
            if profile_image:
                return Response({
                    'profile_photo_url': request.build_absolute_uri(profile_image.original_image.url),
                    'thumbnail_url': request.build_absolute_uri(profile_image.thumbnail.url) if profile_image.thumbnail else None,
                    'created_at': profile_image.created_at,
                    'id': profile_image.id
                })
            return Response({
                'profile_photo_url': None,
                'message': 'No profile photo uploaded yet'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Upload a new profile photo"""
        serializer = UserProfilePhotoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            from images.models import UserImage
            
            # Delete old profile photos
            UserImage.objects.filter(
                user=request.user,
                image_type='PROFILE'
            ).delete()
            
            # Create new profile photo
            profile_image = UserImage.objects.create(
                user=request.user,
                external_id=request.user.external_id or '',
                image_type='PROFILE',
                original_image=serializer.validated_data['profile_photo'],
                original_filename=serializer.validated_data['profile_photo'].name
            )
            
            return Response({
                'success': True,
                'message': 'Profile photo uploaded successfully',
                'profile_photo': {
                    'id': profile_image.id,
                    'url': request.build_absolute_uri(profile_image.original_image.url),
                    'thumbnail_url': request.build_absolute_uri(profile_image.thumbnail.url) if profile_image.thumbnail else None,
                    'created_at': profile_image.created_at
                }
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MyWalletView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        serializer = WalletSerializer(wallet)
        return Response(serializer.data)


class MyReferralsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReferralSerializer

    def get_queryset(self):
        return Referral.objects.filter(referrer=self.request.user).order_by('-created_at')


class NotificationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        notif = serializer.save(user=self.request.user)
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(f'user_{self.request.user.id}', {'type': 'notification', 'notification': NotificationSerializer(notif).data})
        except Exception:
            pass


class NotificationRUDView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class RoadieStatusUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'RODIE':
            return Response({'error': 'Only roadies can update status'}, status=status.HTTP_403_FORBIDDEN)
        is_online = request.data.get('is_online')
        if is_online is None:
            return Response({'error': 'is_online field required'}, status=status.HTTP_400_BAD_REQUEST)
        request.user.is_online = bool(is_online)
        request.user.save() 
        try:
            if get_channel_layer and async_to_sync:
                channel_layer = get_channel_layer()
                group_user = f'user_{request.user.id}'
                group_rodie = f'rodie_{request.user.id}'
                async_to_sync(channel_layer.group_send)(group_user, {'type': 'user.status', 'is_online': request.user.is_online, 'user_id': request.user.id})
                async_to_sync(channel_layer.group_send)(group_rodie, {'type': 'rodie.status', 'is_online': request.user.is_online, 'rodie_id': request.user.id})
        except Exception:
            pass
        return Response({'is_online': request.user.is_online})


class PlatformConfigView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        cfg = PlatformConfig.objects.first()
        if not cfg:
            cfg = PlatformConfig.objects.create()
        serializer = PlatformConfigSerializer(cfg)
        return Response(serializer.data)

    def post(self, request):
        cfg = PlatformConfig.objects.first()
        if not cfg:
            cfg = PlatformConfig.objects.create()
        serializer = PlatformConfigSerializer(cfg, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DepositView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        import uuid
        from .pesapal import PesapalClient
        
        reference = f"DEP-{uuid.uuid4().hex[:12].upper()}"
        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='DEPOSIT',
            status='PENDING',
            reference=reference,
            description=f"Deposit of {amount}"
        )

        try:
            client = PesapalClient()
            callback_url = request.build_absolute_uri('/api/users/wallet/callback/') 
            response = client.submit_order(payment, callback_url)
            tracking_id = response.get('order_tracking_id')
            payment.processor_id = tracking_id
            payment.save()

            phone_number = request.data.get('phone_number')
            stk_response = None
            if phone_number:
                try:
                    stk_response = client.submit_mobile_payment(tracking_id, phone_number)
                except Exception as stk_e:
                    pass

            return Response({
                'payment_id': payment.id,
                'redirect_url': response.get('redirect_url'),
                'reference': reference,
                'stk_pushed': stk_response is not None and stk_response.get('status') == '200'
            })
        except Exception as e:
            payment.status = 'FAILED'
            payment.save()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WithdrawView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = WithdrawSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        if wallet.balance < amount:
            return Response({'error': 'Insufficient funds'}, status=status.HTTP_400_BAD_REQUEST)

        wallet.balance -= amount
        wallet.save()

        import uuid
        reference = f"WTH-{uuid.uuid4().hex[:12].upper()}"
        
        Payment.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='WITHDRAWAL',
            status='PENDING', 
            reference=reference,
            description=f"Withdrawal request to {serializer.validated_data.get('phone_number', request.user.phone)}"
        )

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=-amount,
            reason=f"Withdrawal request {reference}"
        )

        return Response({'message': 'Withdrawal request submitted', 'reference': reference})


class RoadiePaymentsView(APIView):
    """
    GET: Retrieve payment history and wallet summary for roadies
    POST: Initiate a deposit payment
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Only roadies can access their payments
        if request.user.role != 'RODIE':
            return Response(
                {'error': 'Only roadies can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get wallet
        wallet, _ = Wallet.objects.get_or_create(user=request.user)

        # Get all payments
        payments = Payment.objects.filter(user=request.user).order_by('-created_at')

        # Get all wallet transactions
        transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')

        # Combine and serialize
        combined = list(payments) + list(transactions)
        combined.sort(key=lambda x: x.created_at, reverse=True)

        # Serialize transaction history
        history_serializer = TransactionHistorySerializer(combined, many=True)

        # Calculate summary stats
        total_deposits = payments.filter(
            transaction_type='DEPOSIT',
            status='COMPLETED'
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or 0

        total_withdrawals = payments.filter(
            transaction_type='WITHDRAWAL',
            status='COMPLETED'
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or 0

        pending_deposits = payments.filter(
            transaction_type='DEPOSIT',
            status='PENDING'
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or 0

        summary = {
            'current_balance': wallet.balance,
            'total_earned': total_deposits,
            'total_withdrawn': total_withdrawals,
            'pending_deposits': pending_deposits,
            'transaction_count': len(combined)
        }

        return Response({
            'summary': summary,
            'transactions': history_serializer.data,
            'wallet_id': wallet.id,
            'user_id': request.user.id,
            'user_external_id': request.user.external_id
        })

    def post(self, request):
        # Only roadies can make deposits
        if request.user.role != 'RODIE':
            return Response(
                {'error': 'Only roadies can make deposits'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        import uuid
        from .pesapal import PesapalClient

        reference = f"DEP-{uuid.uuid4().hex[:12].upper()}"
        payment = Payment.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='DEPOSIT',
            status='PENDING',
            reference=reference,
            description=f"Wallet Deposit - {amount} KES"
        )

        try:
            client = PesapalClient()
            callback_url = request.build_absolute_uri('/api/users/wallet/callback/')
            response = client.submit_order(payment, callback_url)
            tracking_id = response.get('order_tracking_id')
            payment.processor_id = tracking_id
            payment.save()

            phone_number = request.data.get('phone_number')
            stk_response = None
            if phone_number:
                try:
                    stk_response = client.submit_mobile_payment(tracking_id, phone_number)
                except Exception as stk_e:
                    pass

            return Response({
                'success': True,
                'payment_id': payment.id,
                'redirect_url': response.get('redirect_url'),
                'reference': reference,
                'amount': str(amount),
                'stk_pushed': stk_response is not None and stk_response.get('status') == '200',
                'message': 'Payment initiated. Complete the payment to add funds to your wallet.'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            payment.status = 'FAILED'
            payment.save()
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Failed to initiate payment. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PesapalIPNView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        tracking_id = request.query_params.get('OrderTrackingId')
        merchant_reference = request.query_params.get('OrderMerchantReference')
        
        if not tracking_id or not merchant_reference:
            return Response({'status': 'ignored'}, status=status.HTTP_200_OK)

        from .pesapal import PesapalClient
        from decimal import Decimal

        try:
            payment = Payment.objects.get(reference=merchant_reference)
        except Payment.DoesNotExist:
            return Response({'status': 'not found'}, status=status.HTTP_404_NOT_FOUND)

        client = PesapalClient()
        status_data = client.get_transaction_status(tracking_id)
        
        if status_data:
            pesapal_status = status_data.get('payment_status_description') 
            
            if pesapal_status == 'COMPLETED' and payment.status != 'COMPLETED':
                payment.status = 'COMPLETED'
                payment.save()
                
                if payment.transaction_type == 'DEPOSIT':
                    wallet, _ = Wallet.objects.get_or_create(user=payment.user)
                    wallet.balance += payment.amount
                    wallet.save()
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=payment.amount,
                        reason=f"Deposit {payment.reference}"
                    )
            elif pesapal_status == 'FAILED':
                payment.status = 'FAILED'
                payment.save()

        return Response({
            'orderNotificationType': request.query_params.get('OrderNotificationType'),
            'orderTrackingId': tracking_id,
            'orderMerchantReference': merchant_reference,
            'status': 200
        })
