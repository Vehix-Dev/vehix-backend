import time
import logging
from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
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
            
            # 2. Check current status - Database is source of truth
            try:
                # Refresh status directly from DB
                req_obj = ServiceRequest.objects.get(id=request_id)
                status = req_obj.status
                cache.set(f"request_status:{request_id}", status, timeout=300)

                if status in ['ACCEPTED', 'CANCELLED', 'COMPLETED']:
                    logger.info(f"🛑 Request {request_id} status is {status}. Stopping offers.")
                    return f"Match completed with status: {status}"
            except ServiceRequest.DoesNotExist:
                logger.error(f"❌ Request {request_id} not found in DB.")
                return "Request Deleted"
            except Exception as e:
                logger.warning(f"⚠️ Status check failed: {e}")

            rodie_id = detail['id']
            distance_km = detail['distance']
            
            # 3. Check if roadie is still valid (Online & Not Busy & Active Location)
            try:
                from users.models import User
                from locations.models import RodieLocation
                from django.utils import timezone
                
                rodie_user = User.objects.get(id=rodie_id)
                
                # Skip if offline
                if not rodie_user.is_online:
                    logger.info(f"📵 Rodie {rodie_id} is offline. Skipping.")
                    continue
                
                # Skip if location is stale (No update in 10 mins)
                ten_mins_ago = timezone.now() - timezone.timedelta(minutes=10)
                if not RodieLocation.objects.filter(rodie=rodie_user, updated_at__gte=ten_mins_ago).exists():
                    logger.info(f"👻 Rodie {rodie_id} has a stale location/ghost. Skipping.")
                    continue

                # Skip if already in an active session (Accepted/Started/En-route)
                if ServiceRequest.objects.filter(rodie=rodie_user, status__in=['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']).exists():
                    logger.info(f"🚧 Rodie {rodie_id} is now busy with another request. Skipping.")
                    continue

                if cache.get(f"rodie_locked:{rodie_id}"):
                    logger.info(f"🔒 Rodie {rodie_id} is locked by another offer. Skipping.")
                    continue
            except User.DoesNotExist:
                continue
            except Exception as e:
                logger.warning(f"⚠️ Availability check failed for rodie {rodie_id}: {e}")
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

            # 6. Live Eligibility Check (direct ORM — we are in a sync Celery worker)
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                is_eligible = User.objects.filter(
                    id=rodie_id,
                    is_online=True,
                    is_active=True,
                    is_approved=True,
                    services_selected=True,  # must have selected services
                    is_deleted=False,
                ).exists()
                if not is_eligible:
                    logger.info(f"📵 Rodie {rodie_id} ineligible (offline/unapproved/no services). Skipping.")
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
                
            # Cleanup turn (lock release BEFORE resetting status to avoid race)
            cache.delete(f"rodie_locked:{rodie_id}")
            cache.delete(f"active_offer:{rodie_id}")
            # Reset DECLINED -> REQUESTED so next roadie sees a fresh status
            current_status = cache.get(f"request_status:{request_id}")
            if current_status == 'DECLINED':
                cache.set(f"request_status:{request_id}", 'REQUESTED', timeout=300)

        # 9. Expiration — inline since there is no separate expire_request function
        try:
            with transaction.atomic():
                req = ServiceRequest.objects.select_for_update().get(id=request_id)
                if req.status == 'REQUESTED':
                    req.status = 'EXPIRED'
                    req.save(update_fields=['status'])
                    cache.set(f"request_status:{request_id}", 'EXPIRED', timeout=300)
                    try:
                        async_to_sync(channel_layer.group_send)(
                            f'request_{request_id}',
                            {'type': 'request_expired', 'status': 'EXPIRED', 'request': {'id': request_id}}
                        )
                        async_to_sync(channel_layer.group_send)(
                            f'rider_{req.rider_id}',
                            {'type': 'request_expired', 'status': 'EXPIRED', 'request': {'id': request_id}}
                        )
                    except Exception:
                        pass
                    logger.info(f"⌛ Request #{request_id} EXPIRED — no roadie accepted")
        except Exception as e:
            logger.error(f"❌ Error expiring request #{request_id}: {e}")
        return "Expired"

    finally:
        # Always release the matching lock
        cache.delete(match_lock_key)

@shared_task(bind=True, max_retries=5)
def process_completion_task(self, request_id):
    """Charge fee and handle referral rewards on completion."""
    from .models import charge_fee_for_request
    try:
        # We call the model method but we are now in worker context
        success = charge_fee_for_request(request_id)
        if not success:
            raise Exception("Fee charging logic failed internally")
        return f"Successfully processed completion for Request #{request_id}"
    except Exception as exc:
        # Retry with exponential backoff if possible
        logger.error(f"❌ Error in process_completion_task for Request #{request_id}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
