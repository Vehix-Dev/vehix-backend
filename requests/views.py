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
    serializer_class = ServiceRequestCreateSerializer

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


class ChatMessageCreateAPIView(generics.CreateAPIView):
    """Create a chat message tied to a ServiceRequest and broadcast via channels.

    This endpoint only creates a message and broadcasts it; no history endpoint is provided.
    """
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
        if user.role != 'RODIE':
            return Response({'detail': 'Only roadies can accept requests'}, status=status.HTTP_403_FORBIDDEN)

        req = get_object_or_404(ServiceRequest, id=pk)
        if req.status != 'REQUESTED':
            return Response({'detail': 'Request is not available for acceptance'}, status=status.HTTP_400_BAD_REQUEST)

        if not RodieService.objects.filter(rodie=user, service=req.service_type).exists():
            return Response({'detail': 'You do not offer this service'}, status=status.HTTP_400_BAD_REQUEST)

        cfg = PlatformConfig.objects.first()
        max_neg = cfg.max_negative_balance if cfg else Decimal('0')
        rodie_wallet, _ = Wallet.objects.get_or_create(user=user)
        if rodie_wallet.balance < Decimal(-max_neg):
            return Response({'detail': 'Rodie wallet below allowed negative balance'}, status=status.HTTP_403_FORBIDDEN)

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

                print(f"DEBUG: Acceptance notifying group request_{req.id}")
                async_to_sync(get_channel_layer().group_send)(
                    f'request_{req.id}', 
                    {
                        'type': 'request.accepted', 
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
                async_to_sync(get_channel_layer().group_send)(f'request_{req.id}', {'type': 'request.enroute', 'data': {'request_id': req.id}})
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
        try:
            if get_channel_layer and async_to_sync:
                async_to_sync(get_channel_layer().group_send)(f'request_{req.id}', {'type': 'request.started', 'data': {'request_id': req.id}})
        except Exception:
            pass
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
                async_to_sync(get_channel_layer().group_send)(f'request_{req.id}', {'type': 'request.completed', 'data': {'request_id': req.id}})
        except Exception:
            pass
        return Response({'detail': 'Service completed'})


class RateServiceRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk):
        try:
            service_request = get_object_or_404(ServiceRequest, pk=pk)
            
            # Validate that the request is completed
            if service_request.status != 'COMPLETED':
                return Response(
                    {'detail': 'You can only rate completed requests'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get rating data
            rating = request.data.get('rating')
            role = request.data.get('role')
            
            if not rating or not role:
                return Response(
                    {'detail': 'Rating and role are required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate rating value (1-5)
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    return Response(
                        {'detail': 'Rating must be between 1 and 5'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'Invalid rating format'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate role
            if role not in ['RIDER', 'RODIE']:
                return Response(
                    {'detail': 'Invalid role'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if user is authorized to rate
            if role == 'RIDER' and service_request.rider_id != request.user.id:
                return Response(
                    {'detail': 'You can only rate as the rider of this request'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if role == 'RODIE' and service_request.rodie_id != request.user.id:
                return Response(
                    {'detail': 'You can only rate as the roadie of this request'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Update the appropriate rating field
            if role == 'RIDER':
                service_request.rider_rating = rating
            elif role == 'RODIE':
                service_request.ROADIE_rating = rating
            
            service_request.save()
            
            # Update the rated user's overall rating
            if role == 'RIDER':
                # Update roadie's rating
                self._update_user_rating(service_request.rodie, 'roadie')
            elif role == 'RODIE':
                # Update rider's rating
                self._update_user_rating(service_request.rider, 'rider')
            
            return Response({
                'detail': 'Rating submitted successfully',
                'rating': rating,
                'role': role
            })
            
        except Exception as e:
            return Response(
                {'detail': f'Error submitting rating: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _update_user_rating(self, user, user_type):
        """Update user's overall rating based on all their completed requests"""
        try:
            if user_type == 'roadie':
                # Get all ratings given to this roadie by riders
                ratings = ServiceRequest.objects.filter(
                    rodie=user,
                    status='COMPLETED',
                    rider_rating__isnull=False
                ).values_list('rider_rating', flat=True)
            else:  # rider
                # Get all ratings given to this rider by roadies
                ratings = ServiceRequest.objects.filter(
                    rider=user,
                    status='COMPLETED',
                    ROADIE_rating__isnull=False
                ).values_list('ROADIE_rating', flat=True)
            
            if ratings:
                avg_rating = sum(ratings) / len(ratings)
                # Update user's rating field (assuming User model has rating field)
                user.rating = round(avg_rating, 1)
                user.save(update_fields=['rating'])
                
        except Exception as e:
            # Log error but don't fail the rating submission
            print(f"Error updating user rating: {e}")
