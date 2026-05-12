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
        from .services import find_nearby_rodies
        
        logger.info(f"🚀 Starting matching task for Request #{request_id} with {len(rodie_details)} initial roadies")
        
        offered_rodie_ids = set()
        # Convert initial details to a working list
        current_rodies = list(rodie_details)

        while (time.time() - total_start) < expiry_seconds:
            # 1. Check current status - Database is source of truth
            try:
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

            # 2. If no roadies in our current list, try to find more nearby
            if not current_rodies:
                logger.info(f"🔍 [Task] No roadies in queue for Request #{request_id}. Searching...")
                try:
                    service_type = ServiceType.objects.get(id=service_type_id)
                    new_found = find_nearby_rodies(service_type, rider_lat, rider_lng)
                    
                    # Filter for roadies we haven't offered to yet
                    for item in new_found:
                        r_id = item['rodie'].id
                        if r_id not in offered_rodie_ids:
                            current_rodies.append({
                                'id': r_id,
                                'distance': float(item['distance'])
                            })
                    
                    if not current_rodies:
                        logger.info(f"⏳ [Task] Still no new roadies for Request #{request_id}. Sleeping 5s...")
                        time.sleep(5)
                        continue
                except Exception as e:
                    logger.error(f"❌ Error during re-scan for roadies: {e}")
                    time.sleep(5)
                    continue

            # 3. Take the next roadie
            detail = current_rodies.pop(0)
            rodie_id = detail['id']
            distance_km = detail['distance']
            offered_rodie_ids.add(rodie_id)
            
            # 4. Check if roadie is still valid (Online & Not Busy & Active Location)
            try:
                from users.models import User
                from locations.models import RodieLocation
                from django.utils import timezone
                
                rodie_user = User.objects.get(id=rodie_id)
                
                # Skip if offline
                if not rodie_user.is_online:
                    logger.info(f"📵 Rodie {rodie_id} is offline. Skipping.")
                    continue
                
                # Skip if heartbeat is stale (Safety check)
                if not cache.get(f"rodie_heartbeat:{rodie_id}"):
                    logger.info(f"👻 Rodie {rodie_id} has no active heartbeat. Skipping.")
                    continue

                # Skip if already in an active session
                if ServiceRequest.objects.filter(rodie=rodie_user, status__in=['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']).exists():
                    logger.info(f"🚧 Rodie {rodie_id} is busy. Skipping.")
                    continue

                if cache.get(f"rodie_locked:{rodie_id}"):
                    logger.info(f"🔒 Rodie {rodie_id} is locked. Skipping.")
                    continue
            except User.DoesNotExist:
                continue
            except Exception as e:
                logger.warning(f"⚠️ Availability check failed for rodie {rodie_id}: {e}")
                continue
                
            # 5. Get actual route info (ETA)
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

            # 6. Construct payload
            try:
                req_obj = ServiceRequest.objects.get(id=request_id)
                service_name = ServiceType.objects.get(id=service_type_id).name
                
                payload = {
                    "id": request_id,
                    "service_id": service_type_id,
                    "service_type_name": service_name,
                    "rider_lat": float(rider_lat),
                    "rider_lng": float(rider_lng),
                    "rider_id": req_obj.rider.id,
                    "rider_username": req_obj.rider.username,
                    "rider_name": req_obj.rider.username,
                    "rider_phone": req_obj.rider.phone,
                    "eta_seconds": duration_s,
                    "distance_meters": distance_m,
                    "distance_km": round(distance_m / 1000.0, 1),
                    "fee": float(service_name == 'Towing' and 50000 or 15000), 
                    "rider": {
                        "id": req_obj.rider.id,
                        "username": req_obj.rider.username,
                        "first_name": req_obj.rider.first_name,
                        "last_name": req_obj.rider.last_name,
                        "phone": req_obj.rider.phone,
                    }
                }
            except Exception as e:
                logger.error(f"❌ Failed to construct payload: {e}")
                continue

            # 7. Lock Rodie and Send offer
            try:
                cache.set(f"rodie_locked:{rodie_id}", request_id, timeout=offer_seconds + 5)
                cache.set(f"active_offer:{rodie_id}", payload, timeout=offer_seconds + 5)
                
                logger.info(f"📡 Sending offer to Rodie {rodie_user.username} ({payload['distance_km']}km away)")
                async_to_sync(channel_layer.group_send)(
                    f"rodie_{rodie_id}",
                    {"type": "offer_request", "request": payload}
                )
                
                # Push Notification for New Offer
                from users.fcm import send_push_notification
                send_push_notification(
                    rodie_user,
                    "New Assist Request!",
                    f"A rider nearby needs {service_name}. Tap to view details.",
                    {
                        "type": "OFFER_REQUEST",
                        "request_id": str(request_id),
                        "status": "OFFERED"
                    }
                )
                
                async_to_sync(channel_layer.group_send)(
                    f"request_{request_id}",
                    {
                        "type": "request_proximity",
                        "distance_km": payload["distance_km"],
                        "eta_seconds": payload["eta_seconds"]
                    }
                )
            except Exception as e:
                logger.error(f"❌ WebSocket notification failed: {e}")

            # 8. Poll for response
            poll_start = time.time()
            while time.time() - poll_start < offer_seconds:
                try:
                    status = cache.get(f"request_status:{request_id}")
                    if status == 'ACCEPTED':
                        cache.delete(f"rodie_locked:{rodie_id}")
                        cache.delete(f"active_offer:{rodie_id}")
                        return f"Accepted by {rodie_id}"
                    if status == 'DECLINED':
                        cache.set(f"request_status:{request_id}", 'REQUESTED', timeout=300)
                        break
                    if status == 'CANCELLED':
                        cache.delete(f"rodie_locked:{rodie_id}")
                        cache.delete(f"active_offer:{rodie_id}")
                        return "Cancelled by rider"
                except Exception:
                    pass
                time.sleep(1)
                
            # Cleanup turn
            cache.delete(f"rodie_locked:{rodie_id}")
            cache.delete(f"active_offer:{rodie_id}")

        # 9. Expiration (Window finished without acceptance)
        try:
            with transaction.atomic():
                req = ServiceRequest.objects.select_for_update().get(id=request_id)
                if req.status == 'REQUESTED':
                    req.status = 'EXPIRED'
                    req.save(update_fields=['status'])
                    cache.set(f"request_status:{request_id}", 'EXPIRED', timeout=300)
                    try:
                        async_to_sync(channel_layer.group_send)(
                            f'rider_{req.rider_id}',
                            {'type': 'request_expired', 'status': 'EXPIRED', 'request': {'id': request_id}}
                        )
                        from users.fcm import send_push_notification
                        from users.models import Notification

                        title = 'Request Expired'
                        body = 'Your service request expired before a roadie could accept it.'
                        if req.rider_id:
                            Notification.objects.create(
                                recipient=req.rider,
                                target_role='SPECIFIC',
                                title=title,
                                message=body,
                                notification_type='URGENT'
                            )
                            send_push_notification(
                                req.rider,
                                title,
                                body,
                                {
                                    'notification_id': str(req.id),
                                    'type': 'request_expired',
                                    'request_id': str(req.id)
                                }
                            )
                    except Exception:
                        pass
                    logger.info(f"⌛ Request #{request_id} EXPIRED after {expiry_seconds}s window")
        except Exception as e:
            logger.error(f"❌ Error expiring request #{request_id}: {e}")
        return "Expired"
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
