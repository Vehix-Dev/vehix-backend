from rest_framework import generics, permissions, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import ServiceRequest
from .admin_serializers import ServiceRequestAdminSerializer
from django.db.models import Q
from locations.models import RodieLocation
from .osrm import get_route_info
from django.shortcuts import get_object_or_404
from decimal import Decimal


class ServiceRequestListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ServiceRequestAdminSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['rider__username', 'rodie__username', 'status']

    def get_queryset(self):
        return ServiceRequest.objects.select_related('rider', 'rodie', 'service_type').all()


class ServiceRequestRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ServiceRequestAdminSerializer

    def get_queryset(self):
        return ServiceRequest.objects.select_related('rider', 'rodie', 'service_type').all()


class RealtimeRiderLocationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not getattr(request.user, 'is_authenticated', False) or getattr(request.user, 'role', None) != 'ADMIN':
            return Response({'detail': 'Admin credentials required'}, status=403)
        q = request.query_params.get('q', None)
        active_statuses = ['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'STARTED']
        qs = ServiceRequest.objects.filter(status__in=active_statuses).select_related('rider').order_by('-updated_at')
        if q:
            qs = qs.filter(Q(rider__username__icontains=q) | Q(rider__first_name__icontains=q) | Q(rider__last_name__icontains=q))
        seen = set()
        results = []
        for req in qs:
            if req.rider_id in seen:
                continue
            seen.add(req.rider_id)
            results.append({
                'request_id': req.id,
                'rider_id': req.rider_id,
                'rider_username': req.rider.username,
                'rider_first_name': req.rider.first_name,
                'rider_last_name': req.rider.last_name,
                'lat': float(req.rider_lat),
                'lng': float(req.rider_lng),
                'status': req.status,
                'service_type': str(req.service_type),
                'updated_at': req.updated_at,
            })
        return Response(results)


class RealtimeRiderMapView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not getattr(request.user, 'is_authenticated', False) or getattr(request.user, 'role', None) != 'ADMIN':
            return Response({'detail': 'Admin credentials required'}, status=403)

        q = request.query_params.get('q', None)
        active_statuses = ['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'STARTED']
        qs = ServiceRequest.objects.filter(status__in=active_statuses).select_related('rider').order_by('-updated_at')
        if q:
            qs = qs.filter(Q(rider__username__icontains=q) | Q(rider__first_name__icontains=q) | Q(rider__last_name__icontains=q))
        seen = set()
        features = []
        for req in qs:
            if req.rider_id in seen:
                continue
            seen.add(req.rider_id)
            features.append({
                'type': 'Feature',
                'properties': {
                    'request_id': req.id,
                    'rider_id': req.rider_id,
                    'rider_username': req.rider.username,
                    'status': req.status,
                    'service_type': str(req.service_type),
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(req.rider_lng), float(req.rider_lat)]
                }
            })
        return Response({'type': 'FeatureCollection', 'features': features})


class ServiceRequestRouteView(APIView):
    """Admin endpoint: return route info for a ServiceRequest (rodie -> rider)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        if not getattr(request.user, 'is_authenticated', False) or getattr(request.user, 'role', None) != 'ADMIN':
            return Response({'detail': 'Admin credentials required'}, status=403)

        req = get_object_or_404(ServiceRequest, id=pk)
        data = {
            'request_id': req.id,
            'status': req.status,
            'rider': {
                'id': req.rider_id,
                'username': req.rider.username,
                'lat': float(req.rider_lat),
                'lng': float(req.rider_lng),
            },
            'timestamps': {
                'created_at': req.created_at,
                'accepted_at': req.accepted_at,
                'en_route_at': req.en_route_at,
                'started_at': req.started_at,
                'completed_at': req.completed_at,
            }
        }

        if req.rodie_id:
            try:
                loc = RodieLocation.objects.get(rodie_id=req.rodie_id)
                data['rodie'] = {'id': req.rodie_id, 'lat': float(loc.lat), 'lng': float(loc.lng)}
                distance_m, duration_s = get_route_info(float(loc.lat), float(loc.lng), float(req.rider_lat), float(req.rider_lng))
                data['route'] = {
                    'distance_meters': distance_m,
                    'eta_seconds': duration_s,
                }
            except RodieLocation.DoesNotExist:
                data['rodie'] = None
                data['route'] = None
        else:
            data['rodie'] = None
            data['route'] = None

        return Response(data)


class AdminAssignRodieView(APIView):
    """Admin endpoint to manually assign a roadie to a REQUESTED service request."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if not getattr(request.user, 'is_authenticated', False) or getattr(request.user, 'role', None) != 'ADMIN':
            return Response({'detail': 'Admin credentials required'}, status=403)

        req = get_object_or_404(ServiceRequest, id=pk)
        if req.status != 'REQUESTED':
            return Response({'detail': 'Request is not available for assignment (current status: %s)' % req.status}, status=400)

        rodie_id = request.data.get('rodie_id')
        if not rodie_id:
            return Response({'detail': 'rodie_id is required'}, status=400)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        rodie = get_object_or_404(User, id=rodie_id, role='RODIE')

        
        from services.models import RodieService
        if not RodieService.objects.filter(rodie=rodie, service=req.service_type).exists():
            return Response({'detail': 'Selected roadie does not offer this service'}, status=400)

        req.rodie = rodie
        req.status = 'ACCEPTED'
        from django.utils import timezone
        req.accepted_at = timezone.now()
        req.save()

        
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(f'request_{req.id}', {'type': 'request.accepted', 'data': {'request_id': req.id, 'rodie_id': rodie.id}})
                async_to_sync(channel_layer.group_send)(f'rodie_{rodie.id}', {'type': 'request.assigned', 'data': {'request_id': req.id}})
        except Exception:
            pass

        return Response({'detail': 'Roadie assigned successfully', 'request_id': req.id, 'rodie_id': rodie.id})
