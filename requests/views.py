from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import ServiceRequest
from .serializers import ServiceRequestCreateSerializer
from .services import find_nearby_rodies
from services.models import RodieService
from locations.utils import calculate_distance_km
from locations.models import RodieLocation
from django.core.cache import cache
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from users.models import Wallet, PlatformConfig
from rest_framework.exceptions import PermissionDenied
from decimal import Decimal

try:
    from .serializers import ChatMessageSerializer
except Exception:
    ChatMessageSerializer = None

from django.shortcuts import get_object_or_404
from django.utils import timezone



class RiderRequestsListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    from .serializers import ServiceRequestSerializer
    serializer_class = ServiceRequestSerializer

    def get_queryset(self):
        user = self.request.user
        qs = ServiceRequest.objects.filter(rider=user).select_related('rodie', 'service_type').order_by('-created_at')
        status_filter = self.request.query_params.get('status')
        if status_filter == 'active':
            qs = qs.filter(status__in=['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'STARTED'])
        else:
            # Only return expired, completed and cancelled for history
            qs = qs.filter(status__in=['COMPLETED', 'CANCELLED', 'EXPIRED'])
        return qs


class RoadieRequestsListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    from .serializers import ServiceRequestSerializer
    serializer_class = ServiceRequestSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role != 'RODIE':
            return ServiceRequest.objects.none()
        qs = ServiceRequest.objects.filter(rodie=user).select_related('rider', 'service_type').order_by('-created_at')
        
        status_filter = self.request.query_params.get('status')
        if status_filter == 'active':
            qs = qs.filter(status__in=['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED'])
        else:
            # Only return expired, completed and cancelled for history
            qs = qs.filter(status__in=['COMPLETED', 'CANCELLED', 'EXPIRED'])
        return qs


class NearbyRodieListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        service_id = request.query_params.get('service_id')
        if not lat or not lng or not service_id:
            return Response(
                {'detail': 'lat, lng and service_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service_type_id = int(service_id)
        except Exception:
            return Response({'detail': 'invalid service_id'}, status=status.HTTP_400_BAD_REQUEST)

        rodie_services = RodieService.objects.filter(
            service=service_type_id,
            rodie__is_active=True,
            rodie__is_online=True
        ).select_related('rodie')

        results = []
        from .osrm import get_route_info

        for rs in rodie_services:
            rodie_id = rs.rodie.id

            # Try cache first
            loc = cache.get(f"rodie_loc:{rodie_id}")

            # Fallback to DB if cache empty
            if not loc:
                try:
                    # Only consider roadies who have updated their location in the last 60 minutes
                    # (Increased from 10m to improve matching reliability)
                    sixty_mins_ago = timezone.now() - timezone.timedelta(minutes=60)
                    db_loc = RodieLocation.objects.filter(
                        rodie_id=rodie_id, 
                        updated_at__gte=sixty_mins_ago
                    ).first()
                    
                    if not db_loc:
                        continue # Stale location, skip

                    loc = {"lat": float(db_loc.lat), "lng": float(db_loc.lng)}
                    cache.set(f"rodie_loc:{rodie_id}", loc, timeout=300)
                except Exception:
                    continue

            dist_km = calculate_distance_km(float(lat), float(lng), float(loc['lat']), float(loc['lng']))
            if dist_km <= 5:
                distance_m, duration_s = get_route_info(loc['lat'], loc['lng'], float(lat), float(lng))
                results.append({
                    'rodie_id': rodie_id,
                    'username': rs.rodie.username,
                    'lat': float(loc['lat']),
                    'lng': float(loc['lng']),
                    'distance_km': dist_km,
                    'eta_seconds': duration_s,
                    'distance_meters': distance_m,
                })

        results.sort(key=lambda x: x['distance_km'])
        return Response(results)


class CreateServiceRequestView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ServiceRequestCreateSerializer

    def dispatch(self, request, *args, **kwargs):
        # Debug logging for auth issues
        print(f"\n🔐 CREATE REQUEST: auth={request.headers.get('Authorization', 'NONE')[:30]}...")
        print(f"🔐 User: {request.user} | Auth: {request.user.is_authenticated if hasattr(request.user, 'is_authenticated') else 'N/A'}")
        return super().dispatch(request, *args, **kwargs)

    def perform_create(self, serializer):
        from django.db import transaction
        
        with transaction.atomic():
            # Lock active requests for this rider to ensure atomicity
            active_request = ServiceRequest.objects.select_for_update().filter(
                rider=self.request.user,
                status__in=['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']
            ).first()

            if active_request:
                from rest_framework.exceptions import ValidationError
                raise ValidationError("You already have an active request. Please complete or cancel it first.")

            # Check wallet balance BEFORE creating the request (prevents orphaned records)
            cfg = PlatformConfig.objects.first()
            max_neg = cfg.max_negative_balance if cfg else Decimal('0')
            rider_wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
            if rider_wallet.balance < Decimal(-max_neg):
                raise PermissionDenied('Rider wallet below allowed maximum negative balance')

            # Save the new request
            request_obj = serializer.save(
                rider=self.request.user,
                status='REQUESTED'
            )

        print(f"\n📍 RIDER REQUEST: {self.request.user.username} requesting {request_obj.service_type.name} at ({request_obj.rider_lat}, {request_obj.rider_lng})")

        nearby_rodies = find_nearby_rodies(
            request_obj.service_type,
            float(request_obj.rider_lat),
            float(request_obj.rider_lng)
        )

        print(f"📡 Found {len(nearby_rodies)} nearby online rodies offering {request_obj.service_type.name}:")
        for item in nearby_rodies:
            rodie = item.get('rodie')
            print(f"  - {rodie.username}: {item['distance']:.2f}km away, is_online={rodie.is_online}")

        filtered = []
        matched_usernames = []
        for item in nearby_rodies:
            rodie = item.get('rodie')
            try:
                rodie_wallet, _ = Wallet.objects.get_or_create(user=rodie)
                can_accept = rodie_wallet.balance >= Decimal(-max_neg)
                if can_accept:
                    filtered.append(item)
                    matched_usernames.append(rodie.username)
                else:
                    print(f"💰 {rodie.username} skipped: Wallet balance ({rodie_wallet.balance}) is too low (Max Neg: {max_neg})")
            except Exception as e:
                print(f"❌ Wallet error for {rodie.username}: {e}")
                filtered.append(item)
                if rodie:
                    matched_usernames.append(getattr(rodie, 'username', 'unknown'))

        filtered = [r for r in filtered if r['rodie'].id != self.request.user.id]
        print(f"✅ FINAL MATCHED RODIES: {[r['rodie'].username for r in filtered]}")

        if not filtered:
            # No roadies available — expire the request immediately and notify rider
            print(f"⚠️ No eligible roadies found for Request #{request_obj.id}. Expiring immediately.")
            request_obj.status = 'EXPIRED'
            request_obj.save(update_fields=['status'])
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'rider_{request_obj.rider.id}',
                    {'type': 'request_expired', 'status': 'EXPIRED', 'request': {'id': request_obj.id}}
                )
            except Exception:
                pass
            return

        # Celery Dispatch: Use external tasks for reliability
        from .services import notify_rodies
        notify_rodies(filtered, request_obj, offer_seconds=15, expiry_seconds=90)
        # mark ephemeral request status in cache so notify worker can poll without DB locks
        try:
            cache.set(f"request_status:{request_obj.id}", 'REQUESTED', timeout=120)
        except Exception:
            pass
        print("Matched Rodies (Final):", matched_usernames)


class ChatMessageListView(generics.ListAPIView):
    """List all chat messages for a specific service request."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatMessageSerializer

    def get_queryset(self):
        from .models_chat import ChatMessage
        request_id = self.kwargs.get('pk')
        req = get_object_or_404(ServiceRequest, id=request_id)
        
        # Verify user is part of this request
        if self.request.user != req.rider and self.request.user != req.rodie:
            raise PermissionDenied("You are not part of this request")
        
        return ChatMessage.objects.filter(service_request=req).order_by('created_at')


class ChatMessageCreateAPIView(generics.CreateAPIView):
    """Create a chat message tied to a ServiceRequest and broadcast via channels."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChatMessageSerializer

    def perform_create(self, serializer):
        req = serializer.validated_data.get('service_request')
        if not (req.rider_id == self.request.user.id or (req.rodie_id and req.rodie_id == self.request.user.id)):
            raise PermissionDenied('Not a participant of this request')

        msg = serializer.save(sender=self.request.user)

        try:
                channel_layer = get_channel_layer()
                group_name = f'request_{req.id}'
                message_data = ChatMessageSerializer(msg).data
                # Standardize as CHAT_MESSAGE and flatten for app-side consistency
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'chat.message',
                        **message_data
                    }
                )
        except Exception:
            pass

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


class AcceptRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        print(f"DEBUG: AcceptRequestView - User {user.id} ({user.role}) trying to accept request {pk}")
        
        if user.role != 'RODIE':
            return Response({'detail': 'Only roadies can accept requests'}, status=status.HTTP_403_FORBIDDEN)

        if not user.is_approved:
            return Response({'detail': 'Your account is not yet approved for service.'}, status=status.HTTP_403_FORBIDDEN)
            
        if not user.is_active:
            return Response({'detail': 'Your account is disabled.'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            try:
                # Use select_for_update to lock the row during this transaction
                req = ServiceRequest.objects.select_for_update().get(id=pk)
            except ServiceRequest.DoesNotExist:
                return Response({'detail': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
                
            # 1. Check if request is still available
            if req.status != 'REQUESTED':
                return Response({'detail': f'Request status is {req.status}, no longer available.'}, status=status.HTTP_400_BAD_REQUEST)

            # 2. Safety check: Ensure the roadie isn't already on another active job
            active_job_exists = ServiceRequest.objects.filter(
                rodie=user,
                status__in=['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']
            ).exists()
            
            if active_job_exists:
                return Response({'detail': 'You already have an active request in progress.'}, status=status.HTTP_400_BAD_REQUEST)

            # 3. Validation checks (Services, Wallet)
            if not RodieService.objects.filter(rodie=user, service=req.service_type).exists():
                return Response({'detail': 'You do not offer this service'}, status=status.HTTP_400_BAD_REQUEST)

            cfg = PlatformConfig.objects.first()
            max_neg = cfg.max_negative_balance if cfg else Decimal('0')
            rodie_wallet, _ = Wallet.objects.get_or_create(user=user)
            if rodie_wallet.balance < Decimal(-max_neg):
                return Response({'detail': 'Rodie wallet below allowed negative balance'}, status=status.HTTP_403_FORBIDDEN)

            # 4. Success - Commit the assignment
            req.rodie = user
            req.status = 'ACCEPTED'
            req.accepted_at = timezone.now()
            req.save()
            
            # Clear location lock if it exists
            cache.delete(f"rodie_locked:{user.id}")
            cache.set(f"request_status:{req.id}", 'ACCEPTED', timeout=3600)

            # 5. Notify parties
            try:
                from .serializers import ServiceRequestSerializer
                serializer = ServiceRequestSerializer(req)
                resp_data = serializer.data
                
                # Include roadie's current location relay
                lat = request.data.get('lat')
                lng = request.data.get('lng')
                if lat and lng:
                    resp_data['roadie_lat'] = float(lat)
                    resp_data['roadie_lng'] = float(lng)

                channel_layer = get_channel_layer()
                
                # Notify Rider via personal channel (critical transition event)
                async_to_sync(channel_layer.group_send)(
                    f"rider_{req.rider.id}",
                    {
                        'type': 'request_accepted',
                        'status': 'ACCEPTED',
                        'request': resp_data
                    }
                )
            except Exception as e:
                print(f"DEBUG: Acceptance notification error: {e}")

            return Response({'detail': 'Request accepted', 'request_id': req.id})


class DeclineRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role != 'RODIE':
            return Response({'detail': 'Only roadies can decline requests'}, status=status.HTTP_403_FORBIDDEN)
        req = get_object_or_404(ServiceRequest, id=pk)
        if req.status != 'REQUESTED':
            return Response({'detail': 'Request is not in a state to be declined'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if get_channel_layer and async_to_sync:
                async_to_sync(get_channel_layer().group_send)(f'request_{req.id}', {'type': 'request.declined', 'request': {'id': req.id, 'rodie_id': user.id}})
        except Exception:
            pass
        try:
            cache.set(f"request_status:{req.id}", 'DECLINED', timeout=300)
        except Exception:
            pass

        return Response({'detail': 'Declined'}, status=status.HTTP_200_OK)


class CancelRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        req = get_object_or_404(ServiceRequest, id=pk)
        
        # Get cancellation reason data
        reason_id = request.data.get('reason_id')
        custom_reason_text = request.data.get('custom_reason_text', '').strip()
        
        # Validate reason is provided
        if not reason_id:
            return Response(
                {'detail': 'Cancellation reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import CancellationReason, RequestCancellation
            cancellation_reason = CancellationReason.objects.get(
                id=reason_id, 
                role=user.role, 
                is_active=True
            )
        except CancellationReason.DoesNotExist:
            return Response(
                {'detail': 'Invalid cancellation reason'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate custom text if required
        if cancellation_reason.requires_custom_text and not custom_reason_text:
            return Response(
                {'detail': 'Please provide additional details for this cancellation reason'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Minimum distance in km (100 meters = 0.1 km)
        MIN_CANCEL_DISTANCE_KM = 0.1

        # Get current locations from request body
        current_lat = request.data.get('current_lat')
        current_lng = request.data.get('current_lng')

        # Calculate distance and time to arrival if applicable
        distance_at_cancellation = None
        time_to_arrival_at_cancellation = None
        
        if req.status == 'ACCEPTED' and req.rodie and current_lat and current_lng:
            try:
                from locations.models import RodieLocation
                rodie_loc = RodieLocation.objects.get(rodie=req.rodie)
                distance_at_cancellation = calculate_distance_km(
                    float(current_lat), float(current_lng),
                    float(rodie_loc.lat), float(rodie_loc.lng)
                )
                
                # Estimate time to arrival (assuming 30 km/h average speed in city)
                time_to_arrival_at_cancellation = int((distance_at_cancellation / 30) * 3600)
            except RodieLocation.DoesNotExist:
                pass

        if user.role == 'RIDER' and req.rider_id == user.id:
            # Rider can cancel if request has not started yet
            if req.status in ['REQUESTED', 'ACCEPTED', 'EN_ROUTE']:
                with transaction.atomic():
                    # Re-fetch with row lock to prevent race conditions
                    req = ServiceRequest.objects.select_for_update().get(id=pk)
                    if req.status not in ['REQUESTED', 'ACCEPTED', 'EN_ROUTE']:
                        return Response(
                            {'detail': f'Request status changed to {req.status}'},
                            status=status.HTTP_409_CONFLICT
                        )
                    req.status = 'CANCELLED'
                    req.save()
                    
                    # Create cancellation record
                    RequestCancellation.objects.create(
                        request=req,
                        cancelled_by=user,
                        reason=cancellation_reason,
                        custom_reason_text=custom_reason_text if cancellation_reason.requires_custom_text else None,
                        distance_at_cancellation=distance_at_cancellation,
                        time_to_arrival_at_cancellation=time_to_arrival_at_cancellation
                    )
                
                try:
                    # Update cache so sequential notification thread stops
                    cache.set(f"request_status:{req.id}", 'CANCELLED', timeout=300)
                    
                    # Unlock the rodie if they had already accepted
                    if req.rodie:
                        cache.delete(f"rodie_locked:{req.rodie.id}")
                    
                    channel_layer = get_channel_layer()
                    cancellation_payload = {
                        "type": "request.cancelled",
                        "status": "CANCELLED",
                        "request_id": req.id,
                        "message": "The Rider has cancelled this request.",
                        "reason": cancellation_reason.reason
                    }
                    
                    if req.rodie:
                        # Post-acceptance: send to the assigned roadie's personal channel
                        async_to_sync(channel_layer.group_send)(
                            f'rodie_{req.rodie.id}',
                            cancellation_payload
                        )
                    else:
                        # Pre-acceptance: broadcast to ALL roadies so the offer popup dismisses
                        async_to_sync(channel_layer.group_send)(
                            'role_RODIE',
                            cancellation_payload
                        )
                    
                    print(f"🚫 Broadcasted cancellation for request {req.id} to all parties")
                except Exception as e:
                    print(f"❌ Error broadcasting cancellation: {e}")
                return Response({'detail': 'Request cancelled successfully'})
            else:
                return Response(
                    {'detail': 'Cannot cancel request: The service has already started.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Rodie can cancel if request is accepted or en_route
        if user.role == 'RODIE' and req.rodie_id == user.id:
            if req.status in ['ACCEPTED', 'EN_ROUTE']:
                # Calculate distance for record keeping if location is provided
                dist_km = None
                if current_lat and current_lng:
                    dist_km = calculate_distance_km(
                        float(current_lat), float(current_lng),
                        float(req.rider_lat), float(req.rider_lng)
                    )
                
                with transaction.atomic():
                    # Re-fetch with row lock to prevent race conditions
                    req = ServiceRequest.objects.select_for_update().get(id=pk)
                    if req.status not in ['ACCEPTED', 'EN_ROUTE']:
                        return Response(
                            {'detail': f'Request status changed to {req.status}'},
                            status=status.HTTP_409_CONFLICT
                        )
                    req.status = 'CANCELLED'
                    req.save()
                    
                    # Create cancellation record
                    RequestCancellation.objects.create(
                        request=req,
                        cancelled_by=user,
                        reason=cancellation_reason,
                        custom_reason_text=custom_reason_text if cancellation_reason.requires_custom_text else None,
                        distance_at_cancellation=dist_km if current_lat and current_lng else None,
                        time_to_arrival_at_cancellation=time_to_arrival_at_cancellation
                    )
                
                try:
                    cache.set(f"request_status:{req.id}", 'CANCELLED', timeout=300)
                    
                    # Unlock the rodie
                    cache.delete(f"rodie_locked:{user.id}")
                    
                    # Broadcast cancellation to rider's personal channel
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'rider_{req.rider.id}',
                        {
                            "type": "request.cancelled",
                            "status": "CANCELLED",
                            "request_id": req.id,
                            "message": "Roadie has cancelled this request.",
                            "reason": cancellation_reason.reason
                        }
                    )
                    
                    print(f"🚫 Roadie cancelled request {req.id} - reason: {cancellation_reason.reason}")
                except Exception as e:
                    print(f"❌ Error broadcasting roadie cancellation: {e}")
                
                return Response({'detail': 'Request cancelled successfully'})
            else:
                return Response(
                    {'detail': f'Cannot cancel request with status {req.status}. Once you arrive, you must fulfill the job.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        return Response({'detail': 'Not authorized to cancel'}, status=status.HTTP_403_FORBIDDEN)


class ArrivedRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role != 'RODIE':
            return Response({'detail': 'Only roadies can confirm arrival'}, status=status.HTTP_403_FORBIDDEN)
        req = get_object_or_404(ServiceRequest, id=pk)
        if req.rodie_id != user.id:
            return Response({'detail': 'Not assigned to you'}, status=status.HTTP_403_FORBIDDEN)
        if req.status != 'EN_ROUTE':
            return Response({'detail': f'Cannot mark arrived: request status is {req.status}, expected EN_ROUTE'}, status=status.HTTP_400_BAD_REQUEST)
        
        req.status = 'ARRIVED'
        req.arrived_at = timezone.now()
        req.save()
        
        try:
            cache.set(f"request_status:{req.id}", 'ARRIVED', timeout=3600)
        except Exception:
            pass
            
        try:
            if get_channel_layer and async_to_sync:
                from .serializers import ServiceRequestSerializer
                data = ServiceRequestSerializer(req).data
                channel_layer = get_channel_layer()
                
                # Send to request group (both rider and roadie are members)
                async_to_sync(channel_layer.group_send)(
                    f'request_{req.id}', 
                    {'type': 'request_arrived', 'status': 'ARRIVED', 'request': data}
                )
        except Exception:
            pass
            
        return Response({'detail': 'Marked as arrived'})


class EnrouteRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role != 'RODIE':
            return Response({'detail': 'Only roadies can set en-route'}, status=status.HTTP_403_FORBIDDEN)
        req = get_object_or_404(ServiceRequest, id=pk)
        if req.rodie_id != user.id:
            return Response({'detail': 'Not assigned to you'}, status=status.HTTP_403_FORBIDDEN)
        if req.status != 'ACCEPTED':
            return Response({'detail': f'Cannot mark en-route: request status is {req.status}, expected ACCEPTED'}, status=status.HTTP_400_BAD_REQUEST)
        req.status = 'EN_ROUTE'
        req.en_route_at = timezone.now()
        req.save()
        try:
            cache.set(f"request_status:{req.id}", 'EN_ROUTE', timeout=3600)
        except Exception:
            pass
        try:
            if get_channel_layer and async_to_sync:
                from .serializers import ServiceRequestSerializer
                data = ServiceRequestSerializer(req).data
                channel_layer = get_channel_layer()
                
                # Send to request group (both rider and roadie are members)
                async_to_sync(channel_layer.group_send)(
                    f'request_{req.id}', 
                    {'type': 'request_enroute', 'request': data}
                )
        except Exception:
            pass
        return Response({'detail': 'Marked en-route'})


class StartRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role != 'RODIE':
            return Response({'detail': 'Only roadies can start service'}, status=status.HTTP_403_FORBIDDEN)
        req = get_object_or_404(ServiceRequest, id=pk)
        if req.rodie_id != user.id:
            return Response({'detail': 'Not assigned to you'}, status=status.HTTP_403_FORBIDDEN)
        if req.status != 'ARRIVED':
            return Response({'detail': f'Cannot start service: request status is {req.status}, expected ARRIVED'}, status=status.HTTP_400_BAD_REQUEST)
        req.status = 'STARTED'
        req.started_at = timezone.now()
        req.save()
        try:
            if get_channel_layer and async_to_sync:
                from .serializers import ServiceRequestSerializer
                data = ServiceRequestSerializer(req).data
                channel_layer = get_channel_layer()
                
                # Send to request group (both rider and roadie are members)
                async_to_sync(channel_layer.group_send)(
                    f'request_{req.id}', 
                    {'type': 'request_started', 'status': 'STARTED', 'request': data}
                )
        except Exception:
            pass
        return Response({'detail': 'Service started'})


class CompleteRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from django.db import transaction
        
        user = request.user
        if user.role != 'RODIE':
            return Response({'detail': 'Only roadies can complete service'}, status=status.HTTP_403_FORBIDDEN)

        try:
            with transaction.atomic():
                # Lock the request record for update
                req = ServiceRequest.objects.select_for_update().get(id=pk)
                
                if req.rodie_id != user.id:
                    return Response({'detail': 'Not assigned to you'}, status=status.HTTP_403_FORBIDDEN)
                
                # Check if already completed to avoid duplicate triggers
                if req.status == 'COMPLETED':
                    return Response({'detail': 'Request already completed'}, status=status.HTTP_200_OK)

                if req.status == 'CANCELLED':
                    return Response({'detail': 'Cannot complete a cancelled request'}, status=status.HTTP_400_BAD_REQUEST)

                if req.status != 'STARTED':
                    return Response({'detail': f'Cannot complete from status {req.status}. Must be STARTED.'}, status=status.HTTP_409_CONFLICT)

                req.status = 'COMPLETED'
                req.completed_at = timezone.now()
                req.save()
                
                # Cache the status for fast lookup in matching tasks
                cache.set(f"request_status:{req.id}", 'COMPLETED', timeout=3600)

        except ServiceRequest.DoesNotExist:
            return Response({'detail': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Completion error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Broadcast COMPLETION immediately to reduce latency for the rider
        try:
            if get_channel_layer and async_to_sync:
                from .serializers import ServiceRequestSerializer
                data = ServiceRequestSerializer(req).data
                channel_layer = get_channel_layer()
                
                # Send to request group (both rider and roadie are members)
                async_to_sync(channel_layer.group_send)(
                    f'request_{req.id}', 
                    {'type': 'request_completed', 'status': 'COMPLETED', 'request': data}
                )
        except Exception as e:
            print(f"\u26a0\ufe0f Error broadcasting completion: {e}")

        # Fee charging is handled by post_save signal in models.py
        # no need for redundant blocking call here
        
        return Response({'detail': 'Service completed'})


class RateServiceRequestView(APIView):
    """Create a rating for a completed service request"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        from .serializers import RatingCreateSerializer, RatingSerializer
        from .models_rating import Rating
        
        print(f"🔍 RATING DEBUG: User {request.user.username} (ID: {request.user.id}) submitting rating for request {pk}")
        print(f"🔍 RATING DEBUG: User current_login_id: {request.user.current_login_id}")
        
        try:
            req = ServiceRequest.objects.get(id=pk)
        except ServiceRequest.DoesNotExist:
            return Response({'detail': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Add service_request to data
        data = request.data.copy()
        data['service_request'] = pk
        
        serializer = RatingCreateSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            print(f"🔍 RATING DEBUG: Serializer valid, creating rating...")
            rating = serializer.save()
            print(f"🔍 RATING DEBUG: Rating created successfully, user login_id after save: {request.user.current_login_id}")
            
            return Response(
                RatingSerializer(rating).data,
                status=status.HTTP_201_CREATED
            )
        else:
            print(f"🔍 RATING DEBUG: Serializer errors: {serializer.errors}")
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request, pk):
        """Get ratings for a specific request"""
        from .serializers import RatingSerializer
        from .models_rating import Rating
        
        try:
            req = ServiceRequest.objects.get(id=pk)
        except ServiceRequest.DoesNotExist:
            return Response({'detail': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        ratings = Rating.objects.filter(service_request=req)
        serializer = RatingSerializer(ratings, many=True)
        return Response(serializer.data)
