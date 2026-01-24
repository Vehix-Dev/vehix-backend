from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.db.models import Q
from .models import RodieLocation
from requests.models import ServiceRequest


class RealtimeLocationsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.query_params.get('q', None)

        rodie_qs = RodieLocation.objects.select_related('rodie').all()
        if q:
            rodie_qs = rodie_qs.filter(Q(rodie__username__icontains=q) | Q(rodie__first_name__icontains=q) | Q(rodie__last_name__icontains=q))
        rodies = []
        for loc in rodie_qs:
            rodies.append({
                'rodie_id': loc.rodie_id,
                'rodie_external_id': getattr(loc.rodie, 'external_id', None),
                'rodie_username': loc.rodie.username,
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
            riders.append({
                'request_id': r.id,
                'rider_id': r.rider_id,
                'rider_external_id': getattr(r.rider, 'external_id', None),
                'rider_username': r.rider.username,
                'lat': float(r.rider_lat),
                'lng': float(r.rider_lng),
                'status': r.status,
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
            features.append({
                'type': 'Feature',
                'properties': {
                    'type': 'rodie',
                    'rodie_id': loc.rodie_id,
                    'rodie_external_id': getattr(loc.rodie, 'external_id', None),
                    'rodie_username': loc.rodie.username,
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
            features.append({
                'type': 'Feature',
                'properties': {
                    'type': 'rider',
                    'request_id': r.id,
                    'rider_id': r.rider_id,
                    'rider_external_id': getattr(r.rider, 'external_id', None),
                    'rider_username': r.rider.username,
                    'status': r.status,
                    'updated_at': r.updated_at,
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [float(r.rider_lng), float(r.rider_lat)]
                }
            })

        return Response({'type': 'FeatureCollection', 'features': features})
