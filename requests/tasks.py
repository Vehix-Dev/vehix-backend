import time
import logging
from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async
from requests.models import ServiceRequest
from services.models import ServiceType

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def sequential_offers_task(self, request_id, rodie_details, rider_lat, rider_lng, service_type_id, offer_seconds=15, expiry_seconds=90):
    """
    Celery task to handle sequential matching of rodies.
    rodie_details: List of dicts with {'id': rodie_id, 'distance': distance_km}
    """
    # --- 1. PREVENT DUPLICATE MATCHING TASKS ---
    match_lock_key = f"matching_lock:{request_id}"
    if not cache.add(match_lock_key, "locked", timeout=expiry_seconds + 10):
        logger.warning(f"⚠️ Matching task already running for Request #{request_id}. Exiting.")
        return "Duplicate Task"

    try:
        channel_layer = get_channel_layer()
        total_start = time.time()
        
        # Import here to avoid circular imports
        from .osrm import get_route_info
        
        logger.info(f"🚀 Starting matching task for Request #{request_id} with {len(rodie_details)} rodies")

        for detail in rodie_details:
            # 1. Stop if overall timeout reached (90s)
            if time.time() - total_start > expiry_seconds:
                logger.info(f"⌛ Total matching window expired for Request #{request_id}")
                break
            
            # 2. Check current status - Use Database as ultimate fallback if cache is empty
            try:
                status = cache.get(f"request_status:{request_id}")
                if status is None:
                    def get_db_status():
                        try:
                            return ServiceRequest.objects.get(id=request_id).status
                        except ServiceRequest.DoesNotExist:
                            return 'CANCELLED'
                    status = async_to_sync(database_sync_to_async(get_db_status))()
                    cache.set(f"request_status:{request_id}", status, timeout=300)

                if status in ['ACCEPTED', 'CANCELLED', 'COMPLETED']:
                    logger.info(f"🛑 Request {request_id} status is {status}. Stopping offers.")
                    return f"Match completed with status: {status}"
            except Exception as e:
                logger.warning(f"⚠️ Status check failed: {e}")

            rodie_id = detail['id']
            distance_km = detail['distance']
            
            # 3. Check if roadie is already locked or busy
            if cache.get(f"rodie_locked:{rodie_id}"):
                logger.info(f"🔒 Rodie {rodie_id} is locked by another offer. Skipping.")
                continue
                
            # 4. Get actual route info (ETA)
            duration_s = None
            distance_m = distance_km * 1000
            
            rodie_loc = cache.get(f"rodie_loc:{rodie_id}")
            if rodie_loc:
                try:
                    route_dist, route_dur = get_route_info(
                        rodie_loc['lat'], rodie_loc['lng'], 
                        rider_lat, rider_lng
                    )
                    if route_dist is not None:
                        distance_m = route_dist
                        duration_s = route_dur
                except Exception as e:
                    logger.warning(f"⚠️ OSRM failed for rodie {rodie_id}: {e}")

            # 5. Construct payload
            try:
                req_obj = ServiceRequest.objects.get(id=request_id)
                service_name = ServiceType.objects.get(id=service_type_id).name
                
                payload = {
                    "id": request_id,
                    "service_id": service_type_id,
                    "service_type_name": service_name,
                    "rider_lat": float(rider_lat),
                    "rider_lng": float(rider_lng),
                    "eta_seconds": duration_s,
                    "distance_meters": distance_m,
                    "distance_km": round(distance_m / 1000.0, 1),
                    "fee": 15000, 
                    "rider": {
                        "id": req_obj.rider.id,
                        "first_name": req_obj.rider.first_name,
                        "last_name": req_obj.rider.last_name,
                        "phone": req_obj.rider.phone,
                    }
                }
            except Exception as e:
                logger.error(f"❌ Failed to fetch request/service info: {e}")
                continue

            # 6. Live Eligibility Check
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                def check_eligibility():
                    return User.objects.filter(id=rodie_id, is_online=True, is_active=True, is_approved=True).exists()
                
                is_eligible = async_to_sync(database_sync_to_async(check_eligibility))()
                if not is_eligible:
                    logger.info(f"📵 Rodie {rodie_id} went offline/disabled. Skipping.")
                    continue
            except Exception as e:
                logger.warning(f"⚠️ Eligibility check failed for {rodie_id}: {e}")

            # 7. Lock Rodie and Send offer
            try:
                cache.set(f"rodie_locked:{rodie_id}", request_id, timeout=offer_seconds + 5)
                cache.set(f"active_offer:{rodie_id}", payload, timeout=offer_seconds + 5)
                
                async_to_sync(channel_layer.group_send)(
                    f"rodie_{rodie_id}",
                    {"type": "offer_request", "request": payload}
                )
                
                async_to_sync(channel_layer.group_send)(
                    f"request_{request_id}",
                    {
                        "type": "request_proximity",
                        "distance_km": payload["distance_km"],
                        "eta_seconds": payload["eta_seconds"]
                    }
                )
                logger.info(f"📡 Offer sent to Rodie {rodie_id}")
            except Exception as e:
                logger.error(f"❌ WebSocket notification failed: {e}")

            # 8. Poll for response
            poll_start = time.time()
            while time.time() - poll_start < offer_seconds:
                try:
                    status = cache.get(f"request_status:{request_id}")
                    if status == 'ACCEPTED':
                        cache.delete(f"rodie_locked:{rodie_id}")
                        return f"Accepted by {rodie_id}"
                    if status == 'DECLINED':
                        cache.set(f"request_status:{request_id}", 'REQUESTED', timeout=300)
                        break
                    if status == 'CANCELLED':
                        return "Cancelled by rider"
                except Exception:
                    pass
                time.sleep(1)
                
            # Cleanup turn
            cache.delete(f"rodie_locked:{rodie_id}")
            cache.delete(f"active_offer:{rodie_id}")

        # 9. Expiration
        from .views import expire_request
        expire_request(request_id)
        return "Expired"

    finally:
        # Always release the matching lock
        cache.delete(match_lock_key)
