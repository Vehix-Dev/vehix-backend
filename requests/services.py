from services.models import RodieService, ServiceType
from locations.utils import calculate_distance_km
from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from threading import Thread
import time
from .osrm import get_route_info
from django.db import transaction
from .models import ServiceRequest

MAX_DISTANCE_KM = 50 # Increased for development/testing


def find_nearby_rodies(service_type, rider_lat, rider_lng):
    """
    Find online Rodies within MAX_DISTANCE_KM who offer the requested service.
    Returns a sorted list by closest distance.
    """
    eligible_rodies = []

    # Filter out busy roadies (those with active requests)
    busy_rodie_ids = ServiceRequest.objects.filter(
        status__in=['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']
    ).exclude(rodie__isnull=True).values_list('rodie_id', flat=True)

    rodie_services = RodieService.objects.filter(
        service=service_type,
        rodie__is_active=True,
        rodie__is_online=True
    ).exclude(rodie_id__in=busy_rodie_ids).select_related('rodie')

    for rs in rodie_services:
        # read ephemeral rodie location from cache; skip if not available
        loc = cache.get(f"rodie_loc:{rs.rodie.id}")
        
        # Fallback to database
        if not loc:
            from locations.models import RodieLocation
            try:
                rl = RodieLocation.objects.get(rodie=rs.rodie)
                loc = {'lat': float(rl.lat), 'lng': float(rl.lng)}
            except RodieLocation.DoesNotExist:
                # Last resort: User model fields
                if rs.rodie.lat and rs.rodie.lng:
                    loc = {'lat': float(rs.rodie.lat), 'lng': float(rs.rodie.lng)}
        
        if not loc:
            print(f"⚠️ No location found for rodie {rs.rodie.username}")
            continue

        try:
            distance = calculate_distance_km(
                rider_lat, rider_lng,
                float(loc.get('lat')), float(loc.get('lng'))
            )
            print(f"📍 {rs.rodie.username} is {distance:.2f}km away")
        except Exception as e:
            print(f"❌ Error calculating distance for {rs.rodie.username}: {e}")
            continue

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

    for r in rodies:
        # Check if request was cancelled before offering to next roadie
        try:
            status = cache.get(f"request_status:{request_id}")
            if status == 'CANCELLED':
                print(f"🚫 Request {request_id} was cancelled - stopping sequential offers before next roadie")
                return
        except Exception:
            pass
            
        if time.time() - start >= expiry_seconds:
            try:
                # Final DB check before expiring
                req = ServiceRequest.objects.get(id=request_id)
                if req.status == 'REQUESTED':
                    req.status = 'EXPIRED'
                    req.save()
            except Exception:
                pass
            break

        rodie = r.get('rodie')
        # Get the distance from find_nearby_rodies result
        distance_km = r.get('distance', 0)
        distance_m = distance_km * 1000
        
        # Try to get route info for ETA
        loc = cache.get(f"rodie_loc:{rodie.id}")
        if loc:
            try:
                route_distance_m, duration_s = get_route_info(loc.get('lat'), loc.get('lng'), rider_lat, rider_lng)
                if route_distance_m is not None:
                    distance_m = route_distance_m
                duration_s = duration_s
            except Exception:
                duration_s = None
        else:
            duration_s = None

        req_obj = ServiceRequest.objects.get(id=request_id)
        payload = {
            "id": request_id, 
            "service_id": service_type_id,
            "service_type_name": ServiceType.objects.get(id=service_type_id).name,
            "rider_lat": float(rider_lat),
            "rider_lng": float(rider_lng),
            "eta_seconds": duration_s,
            "distance_meters": distance_m,
            "distance_km": round((distance_m or 0) / 1000.0, 1),
            "fee": 15000,  # Placeholder for now
            "rider_username": req_obj.rider.username,
            "rider_phone": req_obj.rider.phone,
            "rider": {
                "id": req_obj.rider.id,
                "first_name": req_obj.rider.first_name,
                "last_name": req_obj.rider.last_name,
                "username": req_obj.rider.username,
                "phone": req_obj.rider.phone,
            }
        }

        try:
            # Persistent offer for reconnection
            cache.set(f"active_offer:{rodie.id}", payload, timeout=offer_seconds + 2)
            
            async_to_sync(channel_layer.group_send)(
                f"rodie_{rodie.id}",
                {"type": "offer.request", "request": payload}
            )

            # Notify Rider about the proximity of this specific roadie being offered
            async_to_sync(channel_layer.group_send)(
                f"request_{request_id}",
                {
                    "type": "request.proximity",
                    "distance_km": payload["distance_km"],
                    "eta_seconds": payload["eta_seconds"]
                }
            )
        except Exception:
            pass
        # Poll for acceptance or decline
        accepted = False # Initialize accepted flag
        start_time = time.time()
        while time.time() - start_time < offer_seconds:
            try:
                status = cache.get(f"request_status:{request_id}")
                if status == 'ACCEPTED':
                    accepted = True
                    break
                if status in ['DECLINED', 'CANCELLED']:
                    # Move to next roadie immediately if declined, or stop entirely if cancelled
                    if status == 'CANCELLED':
                        print(f"🚫 Request {request_id} was cancelled by rider - stopping sequential offers")
                        return  # Exit the entire function
                    break
            except Exception:
                pass
            time.sleep(1)
        
        # Clear active offer after turn ends
        try:
            cache.delete(f"active_offer:{rodie.id}")
        except Exception:
            pass

        if accepted:
            break

    # Check if request was accepted, cancelled, or needs expiry
    try:
        from django.db import transaction
        with transaction.atomic():
            req = ServiceRequest.objects.get(id=request_id)
            # Only expire if still REQUESTED (not accepted or cancelled)
            if req.status == 'REQUESTED':
                req.status = 'EXPIRED'
                req.save()
                # update cache and notify
                try:
                    cache.set(f"request_status:{req.id}", 'EXPIRED', timeout=300)
                    async_to_sync(channel_layer.group_send)(f'request_{req.id}', {'type': 'request.expired', 'request': {'id': req.id}})
                except Exception:
                    pass
            elif req.status == 'CANCELLED':
                print(f"🚫 Request {request_id} was cancelled - not expiring")
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
