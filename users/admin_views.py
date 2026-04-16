from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Count, Q
from .admin_serializers import AdminUserSerializer
from .admin_serializers import AdminCreateSerializer
from requests.models import ServiceRequest 
from rest_framework import generics, permissions
from .serializers import WalletSerializer, ReferralSerializer, PlatformConfigSerializer, NotificationSerializer
from .models import Wallet, Referral, PlatformConfig, Notification
try:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
except Exception:
    async_to_sync = None
    get_channel_layer = None

from .fcm import send_push_notification, broadcast_role_push
User = get_user_model()



class AdminRegisterView(generics.CreateAPIView):
    serializer_class = AdminCreateSerializer
    permission_classes = [permissions.AllowAny]


class RiderListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = AdminUserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'username']

    def get_queryset(self):
        return User.objects.filter(role='RIDER', is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(role='RIDER')


class RiderRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        return User.objects.filter(role='RIDER', is_deleted=False)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save()
        try:
            if get_channel_layer and async_to_sync:
                channel_layer = get_channel_layer()
                group = f'user_{instance.id}'
                async_to_sync(channel_layer.group_send)(group, {'type': 'user.status', 'is_deleted': True, 'user_id': instance.id})
        except Exception:
            pass
        return Response(status=204)
    
    def get(self, request, *args, **kwargs):
        """Override GET to include summary statistics"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        rider_requests = ServiceRequest.objects.filter(rider=instance)
        total_requests = rider_requests.count()
        
        status_breakdown = rider_requests.values('status').annotate(
            count=Count('status')
        ).order_by('status')
        
        status_dict = {item['status']: item['count'] for item in status_breakdown}
        completed_requests = rider_requests.filter(status='COMPLETED').count()
        active_statuses = ['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'STARTED']
        active_requests = rider_requests.filter(status__in=active_statuses).count()
        service_breakdown = rider_requests.values(
            'service_type__name', 'service_type__code'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]  
        
        recent_requests = rider_requests.order_by('-created_at')[:5].values(
            'id', 'service_type__name', 'status', 'created_at', 'rodie__username'
        )
        
        completion_rate = (completed_requests / total_requests * 100) if total_requests > 0 else 0
        
        summary_data = {
            'stats': {
                'total_requests': total_requests,
                'completed_requests': completed_requests,
                'active_requests': active_requests,
                'cancelled_requests': status_dict.get('CANCELLED', 0),
                'completion_rate': round(completion_rate, 1),
                'status_breakdown': status_dict,
            },
            'service_breakdown': list(service_breakdown),
            'recent_requests': list(recent_requests),
            'created_date': instance.created_at,
            'last_active': rider_requests.order_by('-updated_at').first().updated_at if rider_requests.exists() else instance.updated_at,
        }
        
        response_data = serializer.data
        response_data['summary'] = summary_data
        try:
            wallet, _ = Wallet.objects.get_or_create(user=instance)
            response_data['wallet'] = WalletSerializer(wallet).data
        except Exception:
            response_data['wallet'] = None

        try:
            from services.models import RodieService
            services_qs = RodieService.objects.filter(rodie=instance).select_related('service')
            response_data['services'] = [{'service_id': s.service.id, 'service_name': s.service.name} for s in services_qs]
        except Exception:
            response_data['services'] = []
        
        return Response(response_data)


class RoadieListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = AdminUserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'username']

    def get_queryset(self):
        return User.objects.filter(role='RODIE', is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(role='RODIE')


class RoadieRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        return User.objects.filter(role='RODIE', is_deleted=False)
    
    def update(self, request, *args, **kwargs):
        """Override update to send WebSocket notification when approval status changes"""
        instance = self.get_object()
        old_approved = instance.is_approved
        print(f"DEBUG: Before update - user {instance.id}, is_approved = {old_approved}")
        
        # Perform the update
        response = super().update(request, *args, **kwargs)
        
        # Refresh instance from database to get latest state
        instance.refresh_from_db()
        new_approved = instance.is_approved
        print(f"DEBUG: After update - user {instance.id}, is_approved = {new_approved}")
        print(f"DEBUG: Approval status changed: {old_approved != new_approved}")
        
        if old_approved != new_approved:
            try:
                if get_channel_layer and async_to_sync:
                    channel_layer = get_channel_layer()
                    # Roadie consumers join group "rodie_{user_id}"
                    group = f'rodie_{instance.id}'
                    
                    if new_approved:
                        # Send approval notification
                        title = "Account Approved"
                        body = "Your Vehix account has been approved! You can now go online."
                        message = {
                            'type': 'account.approved',
                            'user_id': instance.id,
                            'is_approved': True,
                            'message': body
                        }
                        print(f" Sent approval WebSocket to roadie {instance.id}")
                    else:
                        # Send unapproval notification
                        title = "Account Unapproved"
                        body = "Your Vehix account has been unapproved. Please contact support."
                        message = {
                            'type': 'account.unapproved',
                            'user_id': instance.id,
                            'is_approved': False,
                            'message': body
                        }
                        print(f" Sent unapproval WebSocket to roadie {instance.id}")
                    
                    # Create persistent notification in database
                    notif = Notification.objects.create(
                        recipient=instance,
                        title=title,
                        message=body,
                        notification_type='SERVICE'
                    )
                    
                    # Send real-time Push Alert
                    send_push_notification(instance, title, body, {
                        'click_action': 'FLUTTER_NOTIFICATION_CLICK',
                        'type': 'account_status',
                        'is_approved': str(new_approved)
                    })
                    
                    async_to_sync(channel_layer.group_send)(group, message)
            except Exception as e:
                print(f" Failed to send approval notification: {e}")
        
        return response
    
    def get(self, request, *args, **kwargs):
        """Override GET to include summary statistics"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        roadie_requests = ServiceRequest.objects.filter(rodie=instance)
        total_assigned = roadie_requests.count()
        
        status_breakdown = roadie_requests.values('status').annotate(
            count=Count('status')
        ).order_by('status')
    
        status_dict = {item['status']: item['count'] for item in status_breakdown}
        completed_requests = roadie_requests.filter(status='COMPLETED').count()
        
        active_statuses = ['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'STARTED']
        active_requests = roadie_requests.filter(status__in=active_statuses).count()
        
        service_breakdown = roadie_requests.values(
            'service_type__name', 'service_type__code'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]  
        
        recent_assignments = roadie_requests.order_by('-created_at')[:5].values(
            'id', 'service_type__name', 'status', 'created_at', 'rider__username'
        )
        
        completion_rate = (completed_requests / total_assigned * 100) if total_assigned > 0 else 0
        
        unique_riders_served = roadie_requests.values('rider').distinct().count()
        
        summary_data = {
            'stats': {
                'total_assignments': total_assigned,
                'completed_assignments': completed_requests,
                'active_assignments': active_requests,
                'cancelled_assignments': status_dict.get('CANCELLED', 0),
                'completion_rate': round(completion_rate, 1),
                'unique_riders_served': unique_riders_served,
                'status_breakdown': status_dict,
            },
            'service_breakdown': list(service_breakdown),
            'recent_assignments': list(recent_assignments),
            'created_date': instance.created_at,
            'last_active': roadie_requests.order_by('-updated_at').first().updated_at if roadie_requests.exists() else instance.updated_at,
            'is_approved': instance.is_approved,
            'rating': 4.5,  
        }
        
        response_data = serializer.data
        response_data['summary'] = summary_data
        try:
            wallet, _ = Wallet.objects.get_or_create(user=instance)
            response_data['wallet'] = WalletSerializer(wallet).data
        except Exception:
            response_data['wallet'] = None
        
        return Response(response_data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save()
        try:
            if get_channel_layer and async_to_sync:
                channel_layer = get_channel_layer()
                group = f'user_{instance.id}'
                async_to_sync(channel_layer.group_send)(group, {'type': 'user.status', 'is_deleted': True, 'user_id': instance.id})
        except Exception:
            pass
        return Response(status=204)


class RealtimeRidersView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.query_params.get('q', None)
        qs = User.objects.filter(role='RIDER', is_active=True, is_deleted=False)
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        serializer = AdminUserSerializer(qs, many=True)
        return Response(serializer.data)


class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        return bool(user and getattr(user, 'is_authenticated', False) and getattr(user, 'role', None) == 'ADMIN' and getattr(user, 'is_active', True))


class AdminListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = AdminCreateSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'username']

    def get_queryset(self):
        return User.objects.filter(role='ADMIN', is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(role='ADMIN', is_staff=True, is_superuser=True, is_approved=True)


class AdminRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        return User.objects.filter(role='ADMIN', is_deleted=False)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save()
        try:
            if get_channel_layer and async_to_sync:
                channel_layer = get_channel_layer()
                group = f'user_{instance.id}'
                async_to_sync(channel_layer.group_send)(group, {'type': 'user.status', 'is_deleted': True, 'user_id': instance.id})
        except Exception:
            pass
        return Response(status=204)

class RiderSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    
    def get(self, request, pk):
        try:
            rider = User.objects.get(id=pk, role='RIDER')
            rider_requests = ServiceRequest.objects.filter(rider=rider)
            
            total_requests = rider_requests.count()
            status_breakdown = rider_requests.values('status').annotate(count=Count('status'))
            
            summary = {
                'rider_id': rider.id,
                'rider_name': f"{rider.first_name} {rider.last_name}",
                'total_requests': total_requests,
                'status_breakdown': {item['status']: item['count'] for item in status_breakdown},
                'completed_requests': rider_requests.filter(status='COMPLETED').count(),
                'active_requests': rider_requests.filter(status__in=['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'STARTED']).count(),
                'created_at': rider.created_at,
                'last_active': rider_requests.order_by('-updated_at').first().updated_at if rider_requests.exists() else None,
            }
            return Response(summary)
        except User.DoesNotExist:
            return Response({'error': 'Rider not found'}, status=404)


class RoadieSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    
    def get(self, request, pk):
        try:
            roadie = User.objects.get(id=pk, role='RODIE')
            roadie_requests = ServiceRequest.objects.filter(rodie=roadie)
            
            total_assignments = roadie_requests.count()
            status_breakdown = roadie_requests.values('status').annotate(count=Count('status'))
            
            summary = {
                'roadie_id': roadie.id,
                'roadie_name': f"{roadie.first_name} {roadie.last_name}",
                'total_assignments': total_assignments,
                'status_breakdown': {item['status']: item['count'] for item in status_breakdown},
                'completed_assignments': roadie_requests.filter(status='COMPLETED').count(),
                'active_assignments': roadie_requests.filter(status__in=['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'STARTED']).count(),
                'unique_riders_served': roadie_requests.values('rider').distinct().count(),
                'is_approved': roadie.is_approved,
                'created_at': roadie.created_at,
                'last_active': roadie_requests.order_by('-updated_at').first().updated_at if roadie_requests.exists() else None,
            }
            return Response(summary)
        except User.DoesNotExist:
            return Response({'error': 'Roadie not found'}, status=404)


class AdminDeletedUsersView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny ]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        return User.objects.filter(is_deleted=True)


class AdminRestoreUserView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk, is_deleted=True)
            user.is_deleted = False
            user.is_active = True
            user.save()
            if get_channel_layer and async_to_sync:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(f'user_{user.id}', {'type': 'user.status', 'is_deleted': False, 'user_id': user.id})
            return Response({'status': 'User restored successfully'})
        except User.DoesNotExist:
            return Response({'error': 'User not found or not deleted'}, status=404)

class AdminWalletListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = WalletSerializer

    def get_queryset(self):
        return Wallet.objects.all()


class AdminWalletRUDView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = WalletSerializer

    def get_queryset(self):
        return Wallet.objects.all()


class AdminReferralListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = ReferralSerializer

    def get_queryset(self):
        return Referral.objects.all()


class AdminReferralRUDView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = ReferralSerializer

    def get_queryset(self):
        return Referral.objects.all()


class AdminPlatformConfigView(APIView):
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


class AdminNotificationListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.all().order_by('-created_at')
    
    def perform_create(self, serializer):
        notif = serializer.save()
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()

            # Prepare payload for WebSockets
            payload = {
                'type': 'notification',
                'notification': NotificationSerializer(notif).data
            }

            # Prepare data for Push Notifications
            push_data = {
                'notification_id': str(notif.id),
                'type': notif.notification_type,
            }

            # 1. Global Broadcast
            if notif.target_role == 'ALL':
                # WebSocket
                async_to_sync(channel_layer.group_send)('notifications', payload)
                # Push
                broadcast_role_push('RIDER', notif.title, notif.message, push_data)
                broadcast_role_push('RODIE', notif.title, notif.message, push_data)
            
            # 2. Role Broadcast
            elif notif.target_role in ['RIDER', 'RODIE']:
                # WebSocket
                async_to_sync(channel_layer.group_send)(f'role_{notif.target_role}', payload)
                # Push
                broadcast_role_push(notif.target_role, notif.title, notif.message, push_data)

            # 3. Individual Broadcast
            elif notif.recipient_id:
                # WebSocket
                async_to_sync(channel_layer.group_send)(f'user_{notif.recipient_id}', payload)
                # Push
                send_push_notification(notif.recipient, notif.title, notif.message, push_data)

        except Exception as e:
            print(f"DEBUG Error in Broadcast: {str(e)}")


class AdminNotificationRUDView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.all()


class AdminUserPasswordView(APIView):
    """Admin endpoint to change/reset passwords for Riders, Roadies and Admins."""
    permission_classes = [permissions.IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            user = User.objects.get(id=pk)
            if user.role not in ('RIDER', 'RODIE', 'ADMIN'):
                return Response({'error': 'Password change only allowed for Riders, Roadies and Admins'}, status=403)
            
            new_password = request.data.get('password')
            if not new_password:
                return Response({'error': 'New password is required'}, status=400)
            
            user.set_password(new_password)
            user.save()
            return Response({'status': 'Password updated successfully'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)