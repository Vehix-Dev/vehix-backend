from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.db.models import Q, Avg, Count
from .models import RodieLocation
from requests.models import ServiceRequest, Rating
from users.models import Wallet


class RealtimeLocationsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.query_params.get('q', None)

        rodie_qs = RodieLocation.objects.select_related('rodie').all()
        if q:
            rodie_qs = rodie_qs.filter(Q(rodie__username__icontains=q) | Q(rodie__first_name__icontains=q) | Q(rodie__last_name__icontains=q))
        rodies = []
        for loc in rodie_qs:
            # Get additional data for rodie
            avg_rating = Rating.objects.filter(rated_user=loc.rodie).aggregate(avg=Avg('rating'))['avg'] or 0
            wallet_balance = getattr(loc.rodie.wallet, 'balance', 0) if hasattr(loc.rodie, 'wallet') else 0
            completed_services = ServiceRequest.objects.filter(rodie=loc.rodie, status='COMPLETED').count()
            last_service = ServiceRequest.objects.filter(rodie=loc.rodie, status='COMPLETED').order_by('-completed_at').first()
            last_service_at = last_service.completed_at if last_service else None
            
            rodies.append({
                'rodie_id': loc.rodie_id,
                'rodie_external_id': getattr(loc.rodie, 'external_id', None),
                'rodie_username': loc.rodie.username,
                'rodie_first_name': getattr(loc.rodie, 'first_name', ''),
                'rodie_last_name': getattr(loc.rodie, 'last_name', ''),
                'average_rating': float(avg_rating),
                'wallet_balance': float(wallet_balance),
                'completed_services_count': completed_services,
                'last_service_at': last_service_at.isoformat() if last_service_at else None,
                'lat': float(loc.lat),
                'lng': float(loc.lng),
                'updated_at': loc.updated_at,
            })

        active_statuses = ['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'STARTED']
        reqs = ServiceRequest.objects.filter(status__in=active_statuses).select_related('rider').order_by('-updated_at')
        if q:
            reqs = reqs.filter(Q(rider__username__icontains=q) | Q(rider__first_name__icontains=q) | Q(rider__last_name__icontains=q))
        seen = set()
        riders = []
        for r in reqs:
            if r.rider_id in seen:
                continue
            seen.add(r.rider_id)
            
            # Get additional data for rider
            wallet_balance = getattr(r.rider.wallet, 'balance', 0) if hasattr(r.rider, 'wallet') else 0
            total_requests = ServiceRequest.objects.filter(rider=r.rider).count()
            
            riders.append({
                'request_id': r.id,
                'rider_id': r.rider_id,
                'rider_external_id': getattr(r.rider, 'external_id', None),
                'rider_username': r.rider.username,
                'rider_first_name': getattr(r.rider, 'first_name', ''),
                'rider_last_name': getattr(r.rider, 'last_name', ''),
                'wallet_balance': float(wallet_balance),
                'total_requests_count': total_requests,
                'current_service_status': r.status,
                'service_type': str(r.service_type),
                'lat': float(r.rider_lat),
                'lng': float(r.rider_lng),
                'updated_at': r.updated_at,
            })

        return Response({'rodies': rodies, 'riders': riders})


class RealtimeLocationsMapView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.query_params.get('q', None)

        features = []

        rodie_qs = RodieLocation.objects.select_related('rodie').all()
        if q:
            rodie_qs = rodie_qs.filter(Q(rodie__username__icontains=q) | Q(rodie__first_name__icontains=q) | Q(rodie__last_name__icontains=q))
        for loc in rodie_qs:
            avg_rating = Rating.objects.filter(rated_user=loc.rodie).aggregate(avg=Avg('rating'))['avg'] or 0
            wallet_balance = getattr(loc.rodie.wallet, 'balance', 0) if hasattr(loc.rodie, 'wallet') else 0
            completed_services = ServiceRequest.objects.filter(rodie=loc.rodie, status='COMPLETED').count()
            last_service = ServiceRequest.objects.filter(rodie=loc.rodie, status='COMPLETED').order_by('-completed_at').first()
            last_service_at = last_service.completed_at if last_service else None
            
            features.append({
                'type': 'Feature',
                'properties': {
                    'type': 'rodie',
                    'rodie_id': loc.rodie_id,
                    'rodie_external_id': getattr(loc.rodie, 'external_id', None),
                    'rodie_username': loc.rodie.username,
                    'rodie_first_name': getattr(loc.rodie, 'first_name', ''),
                    'rodie_last_name': getattr(loc.rodie, 'last_name', ''),
                    'average_rating': float(avg_rating),
                    'wallet_balance': float(wallet_balance),
                    'completed_services_count': completed_services,
                    'last_service_at': last_service_at.isoformat() if last_service_at else None,
                    'updated_at': loc.updated_at,
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(loc.lng), float(loc.lat)]
                }
            })

        active_statuses = ['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'STARTED']
        reqs = ServiceRequest.objects.filter(status__in=active_statuses).select_related('rider').order_by('-updated_at')
        if q:
            reqs = reqs.filter(Q(rider__username__icontains=q) | Q(rider__first_name__icontains=q) | Q(rider__last_name__icontains=q))
        seen = set()
        for r in reqs:
            if r.rider_id in seen:
                continue
            seen.add(r.rider_id)
            
            # Get additional data for rider
            wallet_balance = getattr(r.rider.wallet, 'balance', 0) if hasattr(r.rider, 'wallet') else 0
            total_requests = ServiceRequest.objects.filter(rider=r.rider).count()
            
            features.append({
                'type': 'Feature',
                'properties': {
                    'type': 'rider',
                    'request_id': r.id,
                    'rider_id': r.rider_id,
                    'rider_external_id': getattr(r.rider, 'external_id', None),
                    'rider_username': r.rider.username,
                    'rider_first_name': getattr(r.rider, 'first_name', ''),
                    'rider_last_name': getattr(r.rider, 'last_name', ''),
                    'wallet_balance': float(wallet_balance),
                    'total_requests_count': total_requests,
                    'current_service_status': r.status,
                    'service_type': str(r.service_type),
                    'updated_at': r.updated_at,
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(r.rider_lng), float(r.rider_lat)]
                }
            })

        return Response({'type': 'FeatureCollection', 'features': features})
