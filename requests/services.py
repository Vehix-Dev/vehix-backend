from locations.models import RodieLocation
from services.models import RodieService
from locations.utils import calculate_distance_km
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from threading import Thread
import time
from .osrm import get_route_info
from django.db import transaction

MAX_DISTANCE_KM = 4 # MVP radius


def find_nearby_rodies(service_type, rider_lat, rider_lng):
    """
    Find Rodies within MAX_DISTANCE_KM who offer the requested service.
    Returns a sorted list by closest distance.
    """
    eligible_rodies = []

    rodie_services = RodieService.objects.filter(
        service=service_type,
        rodie__is_active=True
    ).select_related('rodie')

    for rs in rodie_services:
        try:
            location = RodieLocation.objects.get(rodie=rs.rodie)
        except RodieLocation.DoesNotExist:
            continue

        distance = calculate_distance_km(
            rider_lat, rider_lng,
            float(location.lat), float(location.lng)
        )

        if distance <= MAX_DISTANCE_KM:
            eligible_rodies.append({
                'rodie': rs.rodie,
                'distance': distance
            })

    return sorted(eligible_rodies, key=lambda x: x['distance'])


def _sequential_offers(rodies, request_id, rider_lat, rider_lng, service_type_id, offer_seconds=10, expiry_seconds=90):
    """Background thread: send offer to each rodie in order, wait `offer_seconds` for acceptance, expire after `expiry_seconds`."""
    channel_layer = get_channel_layer()
    start = time.time()
    from .models import ServiceRequest

    for r in rodies:
        # check expiry
        if time.time() - start >= expiry_seconds:
            try:
                req = ServiceRequest.objects.get(id=request_id)
                if req.status == 'REQUESTED':
                    req.status = 'EXPIRED'
                    req.save()
            except Exception:
                pass
            break

        rodie = r.get('rodie')
        try:
            loc = RodieLocation.objects.get(rodie=rodie)
            distance_m, duration_s = get_route_info(loc.lat, loc.lng, rider_lat, rider_lng)
        except Exception:
            distance_m, duration_s = None, None

        payload = {
            "request_id": request_id,
            "service_id": service_type_id,
            "service_name": str(service_type_id),
            "rider_lat": float(rider_lat),
            "rider_lng": float(rider_lng),
            "eta_seconds": duration_s,
            "distance_meters": distance_m,
        }

        try:
            async_to_sync(channel_layer.group_send)(
                f"rodie_{rodie.id}",
                {"type": "offer.request", "data": payload}
            )
        except Exception:
            pass
        waited = 0.0
        interval = 0.5
        accepted = False
        while waited < offer_seconds:
            time.sleep(interval)
            waited += interval
            try:
                req = ServiceRequest.objects.select_for_update().get(id=request_id)
                if req.status == 'ACCEPTED':
                    accepted = True
                    break
                if req.status in ('CANCELLED', 'EXPIRED'):
                    accepted = False
                    break
            except Exception:
                pass

        if accepted:
            break

    # If the loop finished and still REQUESTED, mark as EXPIRED
    try:
        from django.db import transaction
        with transaction.atomic():
            req = ServiceRequest.objects.select_for_update().get(id=request_id)
            if req.status == 'REQUESTED':
                req.status = 'EXPIRED'
                req.save()
                # Notify rider
                async_to_sync(channel_layer.group_send)(f'request_{req.id}', {'type': 'request.expired', 'data': {'request_id': req.id}})
    except Exception:
        pass


def notify_rodies(rodies, request_obj, offer_seconds=10, expiry_seconds=90):
    """Start a background thread to offer the request to rodies one-by-one."""
    try:
        t = Thread(target=_sequential_offers, args=(rodies, request_obj.id, request_obj.rider_lat, request_obj.rider_lng, request_obj.service_type.id, offer_seconds, expiry_seconds), daemon=True)
        t.start()
    except Exception:
        channel_layer = get_channel_layer()
        for r in rodies:
            try:
                async_to_sync(channel_layer.group_send)(
                    f"rodie_{r['rodie'].id}",
                    {
                        "type": "send_request",
                        "data": {
                            "request_id": request_obj.id,
                            "service_id": request_obj.service_type.id,
                            "service_name": str(request_obj.service_type),
                            "rider_id": request_obj.rider.id,
                            "rider_name": request_obj.rider.get_full_name(),
                            "lat": float(request_obj.rider_lat),
                            "lng": float(request_obj.rider_lng),
                        }
                    }
                )
            except Exception:
                pass
