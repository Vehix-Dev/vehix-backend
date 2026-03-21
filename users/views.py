from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
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
            phone_number = request.data.get('phone_number')
            response = client.submit_order(payment, callback_url, phone_number)
            tracking_id = response.get('order_tracking_id')
            payment.processor_id = tracking_id
            payment.save()

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
        phone_number = serializer.validated_data.get('phone_number', request.user.phone)

        # Get or create wallet
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        
        # Check sufficient funds
        if wallet.balance < amount:
            return Response({
                'error': 'Insufficient funds', 
                'available_balance': str(wallet.balance),
                'requested_amount': str(amount)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check minimum withdrawal amount (e.g., 100 UGX)
        if amount < 100:
            return Response({
                'error': 'Minimum withdrawal amount is 100 UGX'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Deduct amount from wallet
            wallet.balance -= amount
            wallet.save()

            # Create withdrawal request
            import uuid
            reference = f"WTH-{uuid.uuid4().hex[:12].upper()}"
            
            payment = Payment.objects.create(
                user=request.user,
                amount=amount,
                transaction_type='WITHDRAWAL',
                status='PENDING', 
                reference=reference,
                description=f"Withdrawal request to {phone_number}"
            )

            # Create wallet transaction
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=-amount,
                reason=f"Withdrawal request {reference}"
            )

            return Response({
                'success': True,
                'message': 'Withdrawal request submitted successfully',
                'reference': reference,
                'amount': str(amount),
                'phone_number': phone_number,
                'new_balance': str(wallet.balance)
            })

        except Exception as e:
            # Refund the amount if something went wrong
            wallet.balance += amount
            wallet.save()
            return Response({
                'error': 'Failed to process withdrawal request',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            callback_url = request.build_absolute_uri('/api/users/payments/pesapal/ipn/')
            phone_number = request.data.get('phone_number')
            response = client.submit_order(payment, callback_url, phone_number)
            tracking_id = response.get('order_tracking_id')
            payment.processor_id = tracking_id
            payment.save()

            stk_response = None
            if phone_number:
                try:
                    stk_response = client.submit_mobile_payment(tracking_id, phone_number)
                except Exception as stk_e:
                    print(f"STK Push failed: {stk_e}")

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


class PaymentStatusView(APIView):
    """
    GET: Check the status of a specific payment
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, reference):
        try:
            payment = Payment.objects.get(reference=reference, user=request.user)
            
            # If payment is still pending, try to get updated status from Pesapal
            if payment.status == 'PENDING' and payment.processor_id:
                try:
                    from .pesapal import PesapalClient
                    client = PesapalClient()
                    status_data = client.get_transaction_status(payment.processor_id)
                    
                    if status_data:
                        pesapal_status = status_data.get('payment_status_description')
                        if pesapal_status == 'COMPLETED':
                            payment.status = 'COMPLETED'
                            payment.save()
                            
                            # Credit wallet if this is a deposit
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
                except Exception as e:
                    print(f"Failed to update payment status: {e}")

            return Response({
                'success': True,
                'payment': {
                    'id': payment.id,
                    'reference': payment.reference,
                    'amount': str(payment.amount),
                    'status': payment.status,
                    'transaction_type': payment.transaction_type,
                    'created_at': payment.created_at,
                    'updated_at': payment.updated_at
                }
            })

        except Payment.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Payment not found'
            }, status=status.HTTP_404_NOT_FOUND)


class PesapalIPNView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        tracking_id = request.query_params.get('OrderTrackingId')
        merchant_reference = request.query_params.get('OrderMerchantReference')
        
        if not tracking_id or not merchant_reference:
            return Response({'status': 'ignored', 'message': 'Missing parameters'}, status=status.HTTP_200_OK)

        from .pesapal import PesapalClient
        from decimal import Decimal

        try:
            payment = Payment.objects.get(reference=merchant_reference)
        except Payment.DoesNotExist:
            return Response({'status': 'not found', 'message': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            client = PesapalClient()
            status_data = client.get_transaction_status(tracking_id)
            
            if not status_data:
                payment.status = 'FAILED'
                payment.save()
                return Response({'status': 'failed', 'message': 'Could not verify payment status'}, status=status.HTTP_400_BAD_REQUEST)
            
            pesapal_status = status_data.get('payment_status_description') 
            print(f"Pesapal IPN - Payment {payment.reference} status: {pesapal_status}")
            
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
                    print(f"Deposit completed: {payment.amount} added to {payment.user.username}'s wallet")
                    
            elif pesapal_status == 'FAILED':
                if payment.status != 'FAILED':
                    payment.status = 'FAILED'
                    payment.save()
                    print(f"Payment failed: {payment.reference}")
                    
        except Exception as e:
            print(f"Pesapal IPN Error: {e}")
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'orderNotificationType': request.query_params.get('OrderNotificationType'),
            'orderTrackingId': tracking_id,
            'orderMerchantReference': merchant_reference,
            'status': 200,
            'payment_status': payment.status
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_feedback(request):
    """
    Submit user feedback to support/CRM
    """
    try:
        message = request.data.get('message', '').strip()
        feedback_type = request.data.get('type', 'app_feedback')
        
        if not message:
            return Response(
                {'error': 'Message cannot be empty'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Here you can:
        # 1. Save to database
        # 2. Send email to support
        # 3. Integrate with CRM system
        # 4. Send notification to admin
        
        # For now, just log it (in production, implement proper storage)
        print(f"Feedback received from {request.user.username}: {message}")
        print(f"Type: {feedback_type}")
        
        return Response(
            {'success': 'Feedback submitted successfully'}, 
            status=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        return Response(
            {'error': 'Failed to submit feedback'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
