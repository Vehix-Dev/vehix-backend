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
from .tasks import sequential_offers_task

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

    print(f"🔍 DEBUG MATCHING: Requesting {service_type.name} at ({rider_lat}, {rider_lng})")
    print(f"🔍 DEBUG MATCHING: Busy Roadies: {list(busy_rodie_ids)}")

    rodie_services = RodieService.objects.filter(
        service=service_type,
        rodie__is_active=True,
        rodie__is_online=True,
        rodie__is_approved=True,
        rodie__services_selected=True,
        rodie__is_deleted=False,
    ).exclude(rodie_id__in=busy_rodie_ids).select_related('rodie')
    
    print(f"🔍 DEBUG MATCHING: Roadies offering this service (Filtered for Active/Online/Approved): {[r.rodie.username for r in rodie_services]}")

    filtered_services = []
    for rs in rodie_services:
        is_locked = cache.get(f"rodie_locked:{rs.rodie_id}")
        
        if is_locked:
            print(f"🔒 {rs.rodie.username} skipped: Currently locked by another offer.")
            continue
            
        # SAFETY: Check for heartbeat with 10-minute window
        if not cache.get(f"rodie_heartbeat:{rs.rodie_id}"):
            print(f"👻 {rs.rodie.username} (ID: {rs.rodie_id}) skipped: No heartbeat in 10m.")
            continue
            
        filtered_services.append(rs)
        print(f"✅ {rs.rodie.username} passed initial filters.")
    
    for rs in filtered_services:
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

    return sorted(eligible_rodies, key=lambdef _sequential_offers(rodies, request_id, rider_lat, rider_lng, service_type_id, offer_seconds=15, expiry_seconds=90):
    """Background thread: send offer to each rodie in order, wait `offer_seconds` for acceptance, expire after `expiry_seconds`."""
    channel_layer = get_channel_layer()
    start_time = time.time()
    offered_rodie_ids = set()

    # Get service type for name
    try:
        service_type = ServiceType.objects.get(id=service_type_id)
    except ServiceType.DoesNotExist:
        return

    while (time.time() - start_time) < expiry_seconds:
        # 1. Check if request is still valid (not accepted or cancelled)
        try:
            status = cache.get(f"request_status:{request_id}")
            if status in ['ACCEPTED', 'CANCELLED', 'COMPLETED']:
                print(f"🛑 Request {request_id} has status {status} - stopping search loop.")
                return
        except Exception:
            pass

        # 2. If we have no roadies to offer to, find more
        if not rodies:
            print(f"🔍 [Search Loop] No current roadies. Scanning for nearby roadies for Request #{request_id}...")
            rodies = find_nearby_rodies(service_type, rider_lat, rider_lng)
            # Filter out roadies we already offered to in this search session
            rodies = [r for r in rodies if r['rodie'].id not in offered_rodie_ids]
            
            if not rodies:
                # Still no roadies? Wait a bit and try again
                print(f"⏳ [Search Loop] Still no roadies found. Sleeping 5s...")
                time.sleep(5)
                continue

        # 3. Take the first roadie and offer the job
        r = rodies.pop(0)
        rodie = r.get('rodie')
        offered_rodie_ids.add(rodie.id)
        
        distance_km = r.get('distance', 0)
        distance_m = distance_km * 1000
        
        # Try to get route info for ETA
        duration_s = None
        loc = cache.get(f"rodie_loc:{rodie.id}")
        if loc:
            try:
                route_distance_m, duration_s = get_route_info(loc.get('lat'), loc.get('lng'), rider_lat, rider_lng)
                if route_distance_m is not None:
                    distance_m = route_distance_m
            except Exception:
                pass

        try:
            req_obj = ServiceRequest.objects.get(id=request_id)
            payload = {
                "id": request_id, 
                "service_id": service_type_id,
                "service_type_name": service_type.name,
                "rider_lat": float(rider_lat),
                "rider_lng": float(rider_lng),
                "eta_seconds": duration_s,
                "distance_meters": distance_m,
                "distance_km": round((distance_m or 0) / 1000.0, 1),
                "fee": float(service_type.fixed_price),
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

            # Mark roadie as locked so they don't get other offers
            cache.set(f"rodie_locked:{rodie.id}", True, timeout=offer_seconds + 2)
            cache.set(f"active_offer:{rodie.id}", payload, timeout=offer_seconds + 2)
            
            print(f"📡 [Search Loop] Sending offer to {rodie.username} ({payload['distance_km']}km away)")
            async_to_sync(channel_layer.group_send)(
                f"rodie_{rodie.id}",
                {"type": "offer.request", "request": payload}
            )

            # Update Rider about proximity
            async_to_sync(channel_layer.group_send)(
                f"request_{request_id}",
                {
                    "type": "request.proximity",
                    "distance_km": payload["distance_km"],
                    "eta_seconds": payload["eta_seconds"]
                }
            )

            # 4. Wait for acceptance/decline/timeout
            wait_start = time.time()
            while time.time() - wait_start < offer_seconds:
                status = cache.get(f"request_status:{request_id}")
                if status == 'ACCEPTED':
                    print(f"✅ Request {request_id} accepted by {rodie.username}")
                    return # Exit loop
                if status in ['DECLINED', 'CANCELLED']:
                    if status == 'CANCELLED':
                        print(f"🚫 Request {request_id} cancelled during wait for {rodie.username}")
                        return # Exit loop
                    print(f"👎 {rodie.username} declined. Moving to next...")
                    break # Break wait, move to next roadie
                time.sleep(1)
            
            # Clear lock after turn
            cache.delete(f"rodie_locked:{rodie.id}")
            cache.delete(f"active_offer:{rodie.id}")

        except Exception as e:
            print(f"❌ [Search Loop] Error offering to {rodie.id}: {e}")
            cache.delete(f"rodie_locked:{rodie.id}")

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


def notify_rodies(rodies, request_obj, offer_seconds=15, expiry_seconds=90):
    """Start a Celery task to offer the request to rodies one-by-one.
    Falls back to a background daemon thread if Celery is unavailable.
    """
    try:
        # Prepare serializable rodie details
        rodie_details = []
        for r in rodies:
            rodie_details.append({
                'id': r['rodie'].id,
                'distance': float(r['distance'])
            })
            
        sequential_offers_task.delay(
            request_id=request_obj.id,
            rodie_details=rodie_details,
            rider_lat=float(request_obj.rider_lat),
            rider_lng=float(request_obj.rider_lng),
            service_type_id=request_obj.service_type.id,
            offer_seconds=offer_seconds,
            expiry_seconds=expiry_seconds
        )
        print(f"\U0001f680 [Celery] Dispatched matching task for Request #{request_obj.id}")
    except Exception as e:
        print(f"\u26a0\ufe0f [Celery] Task dispatch failed for Request #{request_obj.id}: {e}")
        print(f"\U0001f504 [Fallback] Starting background thread matching for Request #{request_obj.id}")
        # Fallback: run matching in a daemon thread so at least the request gets dispatched
        Thread(
            target=_sequential_offers,
            args=(rodies, request_obj.id, float(request_obj.rider_lat), float(request_obj.rider_lng), request_obj.service_type.id),
            kwargs={'offer_seconds': offer_seconds, 'expiry_seconds': expiry_seconds},
            daemon=True,
            name=f"matching-req-{request_obj.id}"
        ).start()
