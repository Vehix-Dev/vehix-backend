from django.db.models import Q, Avg
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.apps import apps

from .models import RodieLocation

ServiceRequest = apps.get_model('service_requests', 'ServiceRequest')
Rating = apps.get_model('service_requests', 'Rating')
RodieService = apps.get_model('services', 'RodieService')

ACTIVE_STATUSES = ['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'STARTED']


def _format_elapsed(seconds):
    if seconds is None:
        return None
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _roadie_active_request(rodie):
    return (
        ServiceRequest.objects.filter(rodie=rodie, status__in=ACTIVE_STATUSES)
        .select_related('rider', 'service_type')
        .order_by('-updated_at')
        .first()
    )


def _roadie_service_types(rodie, active_request=None):
    if active_request and active_request.service_type:
        return [active_request.service_type.name]
    try:
        return list(
            RodieService.objects.filter(rodie=rodie)
            .select_related('service')
            .values_list('service__name', flat=True)
        )
    except Exception:
        return []


class RealtimeLocationsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.query_params.get('q', None)
        now = timezone.now()

        rodie_qs = (
            RodieLocation.objects.select_related('rodie')
            .filter(rodie__is_online=True, rodie__is_deleted=False)
        )
        if q:
            rodie_qs = rodie_qs.filter(
                Q(rodie__username__icontains=q)
                | Q(rodie__first_name__icontains=q)
                | Q(rodie__last_name__icontains=q)
                | Q(rodie__external_id__icontains=q)
            )

        rodies = []
        for loc in rodie_qs:
            rodie = loc.rodie
            active_request = _roadie_active_request(rodie)
            on_job = active_request is not None
            avg_rating = (
                Rating.objects.filter(rated_user=rodie).aggregate(avg=Avg('rating'))['avg'] or 0
            )
            wallet_balance = getattr(rodie.wallet, 'balance', 0) if hasattr(rodie, 'wallet') else 0
            completed_services = ServiceRequest.objects.filter(
                rodie=rodie, status='COMPLETED'
            ).count()
            last_service = (
                ServiceRequest.objects.filter(rodie=rodie, status='COMPLETED')
                .order_by('-completed_at')
                .first()
            )
            last_service_at = last_service.completed_at if last_service else None
            service_types = _roadie_service_types(rodie, active_request)

            assigned_rider = None
            if on_job and active_request.rider:
                assigned_rider = {
                    'rider_id': active_request.rider_id,
                    'rider_external_id': getattr(active_request.rider, 'external_id', None),
                    'rider_username': active_request.rider.username,
                    'rider_first_name': getattr(active_request.rider, 'first_name', ''),
                    'rider_last_name': getattr(active_request.rider, 'last_name', ''),
                    'request_id': active_request.id,
                }

            rodies.append({
                'rodie_id': loc.rodie_id,
                'rodie_external_id': getattr(rodie, 'external_id', None),
                'rodie_username': rodie.username,
                'rodie_first_name': getattr(rodie, 'first_name', ''),
                'rodie_last_name': getattr(rodie, 'last_name', ''),
                'rodie_phone': getattr(rodie, 'phone', '') or '',
                'activity_status': 'ON_JOB' if on_job else 'AVAILABLE',
                'service_types': service_types,
                'service_type': service_types[0] if len(service_types) == 1 else None,
                'assigned_rider': assigned_rider,
                'active_request_id': active_request.id if active_request else None,
                'average_rating': float(avg_rating),
                'wallet_balance': float(wallet_balance),
                'completed_services_count': completed_services,
                'last_service_at': last_service_at.isoformat() if last_service_at else None,
                'lat': float(loc.lat),
                'lng': float(loc.lng),
                'updated_at': loc.updated_at,
            })

        reqs = (
            ServiceRequest.objects.filter(status__in=ACTIVE_STATUSES)
            .select_related('rider', 'rodie', 'service_type')
            .order_by('-updated_at')
        )
        if q:
            reqs = reqs.filter(
                Q(rider__username__icontains=q)
                | Q(rider__first_name__icontains=q)
                | Q(rider__last_name__icontains=q)
                | Q(rider__external_id__icontains=q)
            )

        seen = set()
        riders = []
        for r in reqs:
            if r.rider_id in seen:
                continue
            seen.add(r.rider_id)

            wallet_balance = getattr(r.rider.wallet, 'balance', 0) if hasattr(r.rider, 'wallet') else 0
            total_requests = ServiceRequest.objects.filter(rider=r.rider).count()
            elapsed_seconds = (now - r.created_at).total_seconds() if r.created_at else None

            roadie_assigned = None
            if r.rodie:
                roadie_assigned = {
                    'rodie_id': r.rodie_id,
                    'rodie_external_id': getattr(r.rodie, 'external_id', None),
                    'rodie_username': r.rodie.username,
                    'rodie_first_name': getattr(r.rodie, 'first_name', ''),
                    'rodie_last_name': getattr(r.rodie, 'last_name', ''),
                }

            riders.append({
                'request_id': r.id,
                'rider_id': r.rider_id,
                'rider_external_id': getattr(r.rider, 'external_id', None),
                'rider_username': r.rider.username,
                'rider_first_name': getattr(r.rider, 'first_name', ''),
                'rider_last_name': getattr(r.rider, 'last_name', ''),
                'rider_phone': getattr(r.rider, 'phone', '') or '',
                'wallet_balance': float(wallet_balance),
                'total_requests_count': total_requests,
                'current_service_status': r.status,
                'status': r.status,
                'service_type': r.service_type.name if r.service_type else str(r.service_type),
                'roadie_assigned': roadie_assigned,
                'rodie_lat': float(r.rodie.lat) if r.rodie and r.rodie.lat else None,
                'rodie_lng': float(r.rodie.lng) if r.rodie and r.rodie.lng else None,
                'time_elapsed_seconds': elapsed_seconds,
                'time_elapsed': _format_elapsed(elapsed_seconds),
                'request_created_at': r.created_at.isoformat() if r.created_at else None,
                'lat': float(r.rider_lat),
                'lng': float(r.rider_lng),
                'updated_at': r.updated_at,
            })

        return Response({'rodies': rodies, 'riders': riders})


class RealtimeLocationsMapView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        view = RealtimeLocationsView()
        view.request = request
        data = view.get(request).data
        features = []

        for r in data.get('rodies', []):
            features.append({
                'type': 'Feature',
                'properties': {**r, 'type': 'rodie'},
                'geometry': {
                    'type': 'Point',
                    'coordinates': [r['lng'], r['lat']],
                },
            })

        for r in data.get('riders', []):
            features.append({
                'type': 'Feature',
                'properties': {**r, 'type': 'rider'},
                'geometry': {
                    'type': 'Point',
                    'coordinates': [r['lng'], r['lat']],
                },
            })

        return Response({'type': 'FeatureCollection', 'features': features})
