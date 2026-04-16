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
        serializer = UserSerializer(request.user, context={'request': request})
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
        serializer = UserSerializer(request.user, context={'request': request})
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
                'user': UserSerializer(request.user, context={'request': request}).data
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
        
        # Get all payments and wallet transactions
        payments = Payment.objects.filter(user=request.user).order_by('-created_at')
        transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')
        
        # Combine and serialize using the history serializer
        combined = list(payments) + list(transactions)
        combined.sort(key=lambda x: x.created_at, reverse=True)
        
        from .serializers import WalletSerializer, TransactionHistorySerializer
        history_data = TransactionHistorySerializer(combined, many=True).data
        wallet_data = WalletSerializer(wallet).data
        wallet_data['transactions'] = history_data  # Overlay combined history
        
        return Response(wallet_data)


class MyReferralsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ReferralSerializer

    def get_queryset(self):
        return Referral.objects.filter(referrer=self.request.user).order_by('-created_at')


class NotificationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        notif = serializer.save(recipient=self.request.user)
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
        return Notification.objects.filter(recipient=self.request.user)


class RoadieStatusUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'RODIE':
            return Response({'error': 'Only roadies can update status'}, status=status.HTTP_403_FORBIDDEN)
        is_online = request.data.get('is_online')
        if is_online is None:
            return Response({'error': 'is_online field required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 1. Enforce account approval for going online
        if bool(is_online) and not request.user.is_approved:
            return Response({
                'error': 'Account Pending Approval'
            }, status=status.HTTP_403_FORBIDDEN)
            
        # 2. Enforce service selection for going online
        if bool(is_online) and not getattr(request.user, 'services_selected', False):
            return Response({
                'error': 'Select a service to provide'
            }, status=status.HTTP_403_FORBIDDEN)

        request.user.is_online = bool(is_online)
        request.user.save() 
        try:
            if get_channel_layer and async_to_sync:
                channel_layer = get_channel_layer()
                group_user = f'user_{request.user.id}'
                group_rodie = f'rodie_{request.user.id}'
                group_riders = 'role_RIDER'

                status_payload = {
                    'type': 'rodie.status', 
                    'is_online': request.user.is_online, 
                    'rodie_id': request.user.id,
                    'username': request.user.username,
                    'lat': float(request.user.lat) if (request.user.is_online and request.user.lat) else None,
                    'lng': float(request.user.lng) if (request.user.is_online and request.user.lng) else None,
                }

                async_to_sync(channel_layer.group_send)(group_user, status_payload)
                async_to_sync(channel_layer.group_send)(group_rodie, status_payload)
                # Broadcast to all riders so their maps update instantly
                async_to_sync(channel_layer.group_send)(group_riders, status_payload)
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
        import uuid
        from .pesapal import PesapalClient

        reference = f"DEP-{uuid.uuid4().hex[:12].upper()}"
        # Amount is 0/placeholder — Pesapal page lets the user set their own amount
        payment = Payment.objects.create(
            user=request.user,
            amount=0,
            transaction_type='DEPOSIT',
            status='PENDING',
            reference=reference,
            description=f"Wallet deposit by {request.user.username}"
        )

        try:
            client = PesapalClient()
            callback_url = request.build_absolute_uri('/api/users/wallet/callback/')
            response = client.submit_order(payment, callback_url, phone_number=None)
            tracking_id = response.get('order_tracking_id')
            payment.processor_id = tracking_id
            payment.save()

            redirect_url = response.get('redirect_url')
            if not redirect_url:
                payment.status = 'FAILED'
                payment.save()
                return Response({'error': 'Could not generate payment link. Please try again.'}, status=status.HTTP_502_BAD_GATEWAY)

            return Response({
                'payment_id': payment.id,
                'redirect_url': redirect_url,
                'reference': reference,
            })
        except Exception as e:
            payment.status = 'FAILED'
            payment.save()
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WithdrawView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        from django.db import transaction
        
        serializer = WithdrawSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        phone_number = serializer.validated_data.get('phone_number', request.user.phone)

        try:
            with transaction.atomic():
                # Lock the wallet row for this user
                wallet = Wallet.objects.select_for_update().filter(user=request.user).first()
                if not wallet:
                    wallet = Wallet.objects.create(user=request.user)
                
                # Check sufficient funds (WITH LOCK)
                if wallet.balance < amount:
                    return Response({
                        'error': 'Insufficient funds', 
                        'available_balance': str(wallet.balance),
                        'requested_amount': str(amount)
                    }, status=status.HTTP_400_BAD_REQUEST)

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
        # Only roadies can make deposits here (though they can also use /wallet/deposit/ now)
        if request.user.role != 'RODIE':
            return Response(
                {'error': 'Only roadies can make deposits'},
                status=status.HTTP_403_FORBIDDEN
            )

        import uuid
        from .pesapal import PesapalClient

        reference = f"DEP-{uuid.uuid4().hex[:12].upper()}"
        payment = Payment.objects.create(
            user=request.user,
            amount=0, # Placeholder, updated via IPN/Status check
            transaction_type='DEPOSIT',
            status='PENDING',
            reference=reference,
            description=f"Wallet deposit by {request.user.username}"
        )

        try:
            client = PesapalClient()
            callback_url = request.build_absolute_uri('/api/users/payments/pesapal/ipn/')
            response = client.submit_order(payment, callback_url, phone_number=None)
            tracking_id = response.get('order_tracking_id')
            payment.processor_id = tracking_id
            payment.save()

            return Response({
                'success': True,
                'payment_id': payment.id,
                'redirect_url': response.get('redirect_url'),
                'reference': reference,
                'message': 'Payment initiated. Proceed to Pesapal to complete your deposit.'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            payment.status = 'FAILED'
            payment.save()
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Failed to initiate payment.'
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
                        # Correctly capture the actual amount paid from Pesapal response
                        actual_amount = status_data.get('amount', payment.amount)
                        payment.amount = actual_amount
                        
                        if pesapal_status == 'COMPLETED':
                            payment.status = 'COMPLETED'
                            payment.save()
                            
                            # Credit wallet if this is a deposit
                            if payment.transaction_type == 'DEPOSIT':
                                wallet, _ = Wallet.objects.get_or_create(user=payment.user)
                                wallet.balance += Decimal(str(actual_amount))
                                wallet.save()
                                WalletTransaction.objects.create(
                                    wallet=wallet,
                                    amount=actual_amount,
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
        from django.db import transaction

        try:
            with transaction.atomic():
                # Lock the payment row to prevent double-processing/race conditions
                try:
                    payment = Payment.objects.select_for_update().get(reference=merchant_reference)
                except Payment.DoesNotExist:
                    return Response({'status': 'not found', 'message': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)

                client = PesapalClient()
                status_data = client.get_transaction_status(tracking_id)
                
                if not status_data:
                    if payment.status == 'PENDING':
                        payment.status = 'FAILED'
                        payment.save()
                    return Response({'status': 'failed', 'message': 'Could not verify payment status'}, status=status.HTTP_400_BAD_REQUEST)
                
                pesapal_status = status_data.get('payment_status_description') 
                actual_amount = status_data.get('amount', payment.amount)
                
                # Check if already processed to avoid double crediting
                if payment.status == 'COMPLETED':
                    return Response({'status': 'already_processed', 'payment_status': 'COMPLETED'})

                payment.amount = actual_amount
                print(f"Pesapal IPN - Payment {payment.reference} status: {pesapal_status}, Amount: {actual_amount}")
                
                if pesapal_status == 'COMPLETED':
                    payment.status = 'COMPLETED'
                    payment.save()
                    
                    if payment.transaction_type == 'DEPOSIT':
                        wallet, _ = Wallet.objects.get_or_create(user=payment.user)
                        wallet.balance += Decimal(str(actual_amount))
                        wallet.save()
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            amount=actual_amount,
                            reason=f"Deposit {payment.reference}"
                        )
                        print(f"Deposit completed: {payment.amount} added to {payment.user.username}'s wallet")
                        
                elif pesapal_status == 'FAILED':
                    payment.status = 'FAILED'
                    payment.save()
                    print(f"Payment failed: {payment.reference}")
                    
        except Exception as e:
            print(f"Pesapal IPN Error: {e}")
            import logging; logging.exception("Pesapal IPN critical error")
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
            {'error': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )


class UserProfilePasswordChangeView(APIView):
    """
    Allow authenticated user to change their own password
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        
        if not current_password or not new_password:
            return Response(
                {'error': 'Current and new password are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        user = request.user
        
        # Verify current password
        if not user.check_password(current_password):
            return Response(
                {'error': 'Invalid current password'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Optional: Additional password strength validation
        if len(new_password) < 6:
            return Response(
                {'error': 'New password must be at least 6 characters'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Set and save new password
        user.set_password(new_password)
        user.save()
        
        return Response({
            'success': True,
            'message': 'Password updated successfully'
        })

from rest_framework import viewsets
from rest_framework.decorators import action
from .models import Notification
from .serializers import NotificationSerializer

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing and managing user notifications
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'marked as read'})

    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        Notification.objects.filter(recipient=self.request.user, is_read=False).update(is_read=True)
        return Response({'status': 'all marked as read'})
