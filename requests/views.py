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
            qs = qs.filter(status__in=['ACCEPTED', 'EN_ROUTE', 'STARTED'])
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
            rodie__is_active=True
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
                    db_loc = RodieLocation.objects.get(rodie_id=rodie_id)
                    loc = {"lat": float(db_loc.lat), "lng": float(db_loc.lng)}
                    cache.set(f"rodie_loc:{rodie_id}", loc, timeout=300)  # cache 5 min
                except RodieLocation.DoesNotExist:
                    continue  # no location info, skip this rodie

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
        cfg = PlatformConfig.objects.first()
        max_neg = cfg.max_negative_balance if cfg else Decimal('0')
        rider_wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        if rider_wallet.balance < Decimal(-max_neg):
            raise PermissionDenied('Rider wallet below allowed maximum negative balance')

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
                if rodie_wallet.balance >= Decimal(-max_neg):
                    filtered.append(item)
                    matched_usernames.append(rodie.username)
            except Exception:
                filtered.append(item)
                if rodie:
                    matched_usernames.append(getattr(rodie, 'username', 'unknown'))

        filtered = [r for r in filtered if r['rodie'].id != self.request.user.id]
        matched_usernames = [r['rodie'].username for r in filtered]
        
        print(f"✅ MATCHED RODIES (after wallet/filters): {matched_usernames}\n")
        
        from requests.services import notify_rodies
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
            if get_channel_layer and async_to_sync:
                channel_layer = get_channel_layer()
                group_name = f'request_{req.id}'
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'chat.message',
                        'message': ChatMessageSerializer(msg).data
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
            print(f"DEBUG: AcceptRequestView - Failed: User role is {user.role}, not RODIE")
            return Response({'detail': 'Only roadies can accept requests'}, status=status.HTTP_403_FORBIDDEN)

        try:
            req = ServiceRequest.objects.get(id=pk)
            print(f"DEBUG: AcceptRequestView - Request {pk} found, status: {req.status}")
        except ServiceRequest.DoesNotExist:
            print(f"DEBUG: AcceptRequestView - Failed: Request {pk} does not exist")
            return Response({'detail': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
            
        if req.status != 'REQUESTED':
            print(f"DEBUG: AcceptRequestView - Failed: Request status is {req.status}, not REQUESTED")
            return Response({'detail': 'Request is not available for acceptance'}, status=status.HTTP_400_BAD_REQUEST)

        if not RodieService.objects.filter(rodie=user, service=req.service_type).exists():
            print(f"DEBUG: AcceptRequestView - Failed: Roadie {user.id} does not offer service {req.service_type.id}")
            return Response({'detail': 'You do not offer this service'}, status=status.HTTP_400_BAD_REQUEST)

        cfg = PlatformConfig.objects.first()
        max_neg = cfg.max_negative_balance if cfg else Decimal('0')
        rodie_wallet, _ = Wallet.objects.get_or_create(user=user)
        print(f"DEBUG: AcceptRequestView - Roadie wallet balance: {rodie_wallet.balance}, max negative: {max_neg}")
        if rodie_wallet.balance < Decimal(-max_neg):
            print(f"DEBUG: AcceptRequestView - Failed: Wallet balance {rodie_wallet.balance} below max negative {-max_neg}")
            return Response({'detail': 'Rodie wallet below allowed negative balance'}, status=status.HTTP_403_FORBIDDEN)

        print(f"DEBUG: AcceptRequestView - All checks passed, accepting request {pk}")
        req.rodie = user
        req.status = 'ACCEPTED'
        req.accepted_at = timezone.now()
        req.save()
        try:
            cache.set(f"request_status:{req.id}", 'ACCEPTED', timeout=3600)
        except Exception:
            pass

        try:
            if get_channel_layer and async_to_sync:
                from .serializers import ServiceRequestSerializer
                serializer = ServiceRequestSerializer(req)
                resp_data = serializer.data
                
                # Include roadie's current location for the map
                loc = cache.get(f"rodie_loc:{user.id}")
                if loc:
                    resp_data['roadie_lat'] = loc.get('lat')
                    resp_data['roadie_lng'] = loc.get('lng')

                print(f"DEBUG: Acceptance notifying groups for request {req.id}")
                print(f"DEBUG: Rider ID: {req.rider.id}, Request ID: {req.id}")
                
                # Send to rider's personal group for guaranteed delivery
                rider_group = f"rider_{req.rider.id}"
                print(f"DEBUG: Sending to rider group: {rider_group}")
                async_to_sync(get_channel_layer().group_send)(
                    rider_group,
                    {
                        'type': 'request_accepted',
                        'status': 'ACCEPTED',
                        'request': resp_data
                    }
                )
                print(f"DEBUG: Sent acceptance to rider group: {rider_group}")
                
                # Also send to request group for backup
                request_group = f'request_{req.id}'
                print(f"DEBUG: Sending to request group: {request_group}")
                async_to_sync(get_channel_layer().group_send)(
                    request_group,
                    {
                        'type': 'request_accepted',
                        'status': 'ACCEPTED', 
                        'request': resp_data
                    }
                )
                print(f"DEBUG: Sent acceptance to request group: {request_group}")
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
        
        # Minimum distance in km (100 meters = 0.1 km)
        MIN_CANCEL_DISTANCE_KM = 0.1

        # Get current locations from request body
        current_lat = request.data.get('current_lat')
        current_lng = request.data.get('current_lng')

        if user.role == 'RIDER' and req.rider_id == user.id:
            # Rider can cancel if request is not yet accepted or in certain statuses
            if req.status in ['REQUESTED', 'ACCEPTED']:
                # Check distance if accepted
                if req.status == 'ACCEPTED' and req.rodie:
                    if current_lat and current_lng:
                        try:
                            # Get rodie's current location
                            rodie_loc = RodieLocation.objects.get(rodie=req.rodie)
                            dist_km = calculate_distance_km(
                                float(current_lat), float(current_lng),
                                float(rodie_loc.lat), float(rodie_loc.lng)
                            )
                            if dist_km < MIN_CANCEL_DISTANCE_KM:
                                return Response(
                                    {
                                        'detail': f'Distance should be more than {int(MIN_CANCEL_DISTANCE_KM * 1000)} meters to cancel',
                                        'min_distance_meters': int(MIN_CANCEL_DISTANCE_KM * 1000),
                                        'current_distance_meters': max(1, int(dist_km * 1000))
                                    },
                                    status=status.HTTP_403_FORBIDDEN
                                )
                        except RodieLocation.DoesNotExist:
                            # No location for rodie, allow cancel
                            pass
                    else:
                        # No location provided, deny for safety
                        return Response(
                            {'detail': 'Current location required to cancel accepted request'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                req.status = 'CANCELLED'
                req.save()
                try:
                    cache.set(f"request_status:{req.id}", 'CANCELLED', timeout=300)
                except Exception:
                    pass
                return Response({'detail': 'Request cancelled successfully'})
            else:
                return Response(
                    {'detail': f'Cannot cancel request with status {req.status}'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Rodie can cancel if request is accepted/en_route/started
        if user.role == 'RODIE' and req.rodie_id == user.id:
            if req.status in ['ACCEPTED', 'EN_ROUTE', 'STARTED']:
                # Check distance
                if current_lat and current_lng:
                    dist_km = calculate_distance_km(
                        float(current_lat), float(current_lng),
                        float(req.rider_lat), float(req.rider_lng)
                    )
                    if dist_km < MIN_CANCEL_DISTANCE_KM:
                        return Response(
                            {
                                'detail': f'Distance should be more than {int(MIN_CANCEL_DISTANCE_KM * 1000)} meters to cancel',
                                'min_distance_meters': int(MIN_CANCEL_DISTANCE_KM * 1000),
                                'current_distance_meters': max(1, int(dist_km * 1000))
                            },
                            status=status.HTTP_403_FORBIDDEN
                        )
                else:
                    # No location provided, deny for safety
                    return Response(
                        {'detail': 'Current location required to cancel'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                req.status = 'CANCELLED'
                req.save()
                try:
                    cache.set(f"request_status:{req.id}", 'CANCELLED', timeout=300)
                except Exception:
                    pass
                return Response({'detail': 'Request cancelled successfully'})
            else:
                return Response(
                    {'detail': f'Cannot cancel request with status {req.status}'},
                    status=status.HTTP_403_FORBIDDEN
                )

        return Response({'detail': 'Not authorized to cancel'}, status=status.HTTP_403_FORBIDDEN)


class EnrouteRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role != 'RODIE':
            return Response({'detail': 'Only roadies can set en-route'}, status=status.HTTP_403_FORBIDDEN)
        req = get_object_or_404(ServiceRequest, id=pk)
        if req.rodie_id != user.id:
            return Response({'detail': 'Not assigned to you'}, status=status.HTTP_403_FORBIDDEN)
        req.status = 'EN_ROUTE'
        req.en_route_at = timezone.now()
        req.save()
        try:
            cache.set(f"request_status:{req.id}", 'EN_ROUTE', timeout=3600)
        except Exception:
            pass
        try:
            if get_channel_layer and async_to_sync:
                async_to_sync(get_channel_layer().group_send)(f'request_{req.id}', {'type': 'request_enroute', 'data': {'request_id': req.id}})
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
        req.status = 'STARTED'
        req.started_at = timezone.now()
        req.save()
        try:
            cache.set(f"request_status:{req.id}", 'STARTED', timeout=3600)
        except Exception:
            pass
        # WebSocket broadcast is handled by post_save signal - no duplicate needed here
        return Response({'detail': 'Service started'})


class CompleteRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        if user.role != 'RODIE':
            return Response({'detail': 'Only roadies can complete service'}, status=status.HTTP_403_FORBIDDEN)
        req = get_object_or_404(ServiceRequest, id=pk)
        if req.rodie_id != user.id:
            return Response({'detail': 'Not assigned to you'}, status=status.HTTP_403_FORBIDDEN)
        req.status = 'COMPLETED'
        req.completed_at = timezone.now()
        req.save()
        try:
            cache.set(f"request_status:{req.id}", 'COMPLETED', timeout=3600)
        except Exception:
            pass
        try:
            from .models import charge_fee_for_request
            charge_fee_for_request(req)
        except Exception:
            pass
        try:
            if get_channel_layer and async_to_sync:
                async_to_sync(get_channel_layer().group_send)(f'request_{req.id}', {'type': 'request_completed', 'data': {'request_id': req.id}})
        except Exception:
            pass
        return Response({'detail': 'Service completed'})


class RateServiceRequestView(APIView):
    """Create a rating for a completed service request"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        from .serializers import RatingCreateSerializer, RatingSerializer
        from .models_rating import Rating
        
        try:
            req = ServiceRequest.objects.get(id=pk)
        except ServiceRequest.DoesNotExist:
            return Response({'detail': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Add service_request to data
        data = request.data.copy()
        data['service_request'] = pk
        
        serializer = RatingCreateSerializer(data=data, context={'request': request})
        
        if serializer.is_valid():
            rating = serializer.save()
            return Response(
                RatingSerializer(rating).data,
                status=status.HTTP_201_CREATED
            )
        
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
