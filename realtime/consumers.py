from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from requests.models import ServiceRequest
from requests.models_chat import ChatMessage
from users.models import RiderAvailabilityLog
from locations.models import RodieLocation
from django.utils import timezone
from django.core.cache import cache
User = get_user_model()


@database_sync_to_async
def cache_set_rodie_location(user_id, lat, lng):
    try:
        lat_f, lng_f = float(lat), float(lng)
        cache.set(f"rodie_loc:{user_id}", {'lat': lat_f, 'lng': lng_f}, timeout=300)
        # Throttle DB writes: only write if last DB write was >30s ago
        db_write_key = f"rodie_loc_db_ts:{user_id}"
        if not cache.get(db_write_key):
            User.objects.filter(id=user_id).update(lat=lat_f, lng=lng_f)
            RodieLocation.objects.update_or_create(
                rodie_id=user_id,
                defaults={'lat': lat_f, 'lng': lng_f, 'updated_at': timezone.now()}
            )
            cache.set(db_write_key, True, timeout=30)
    except Exception:
        pass

@database_sync_to_async
def cache_set_rider_location(user_id, lat, lng):
    try:
        lat_f, lng_f = float(lat), float(lng)
        cache.set(f"rider_loc:{user_id}", {'lat': lat_f, 'lng': lng_f}, timeout=300)
        User.objects.filter(id=user_id).update(lat=lat_f, lng=lng_f)
    except Exception:
        pass


@database_sync_to_async
def cache_get_rodie_location(user_id):
    try:
        return cache.get(f"rodie_loc:{user_id}")
    except Exception:
        return None

class AdminConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated or user.role != "ADMIN":
            await self.close()
            return

        self.group_name = "admin_monitoring"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def request_update(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "data": event["data"]})

    async def rodie_location(self, event):
        await self.send_json({
            "type": "RODIE_LOCATION",
            "rodie_id": event.get("rodie_id"),
            "lat": event["lat"],
            "lng": event["lng"]
        })

    async def rider_location(self, event):
        await self.send_json({
            "type": "RIDER_LOCATION",
            "rider_id": event.get("rider_id"),
            "lat": event["lat"],
            "lng": event["lng"]
        })

class RodieConsumer(AsyncJsonWebsocketConsumer):
    @database_sync_to_async
    def _set_online(self, user, online):
        from users.models import User
        User.objects.filter(id=user.id).update(is_online=online)

    async def connect(self):
        user = self.scope["user"]
        try:
            if not user.is_authenticated:
                print(f"❌ [RodieConsumer] Auth failed - user is AnonymousUser")
                await self.close()
                return
            print(f"🔌 [RodieConsumer] Connection attempt from user {user.id}")
            if user.role != "RODIE":
                print(f"❌ [RodieConsumer] Auth failed - Role: {user.role} (expected RODIE)")
                await self.close()
                return

            # ACCEPT immediately to allow group operations
            await self.accept()

            self.group_name = f"rodie_{user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.channel_layer.group_add(f'role_{user.role}', self.channel_name)
            await self.channel_layer.group_add('notifications', self.channel_name)
            
            # --- AUTO-REJOIN ACTIVE REQUESTS ---
            try:
                from requests.models import ServiceRequest
                from django.db.models import Q
                def get_active_request_id():
                    req = ServiceRequest.objects.filter(
                        rodie_id=user.id,
                        status__in=['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']
                    ).first()
                    return req
                
                req = await database_sync_to_async(get_active_request_id)()
                if req:
                    await self.channel_layer.group_add(f"request_{req.id}", self.channel_name)
                    print(f"🔄 [RodieConsumer] Auto-rejoined request group: request_{req.id}")
                    
                    # Send current state immediately to sync UI
                    from requests.serializers import ServiceRequestSerializer
                    serializer_data = await database_sync_to_async(lambda: ServiceRequestSerializer(req).data)()
                    await self.send_json({
                        "type": "REQUEST_UPDATE",
                        "status": req.status,
                        "request": serializer_data
                    })
            except Exception as e:
                print(f"⚠️ [RodieConsumer] Error auto-rejoining active request: {e}")

            # Mark as alive immediately upon connection (10-minute safety window)
            await database_sync_to_async(cache.set)(f"rodie_heartbeat:{user.id}", True, timeout=600)
            print(f"💓 [Heartbeat] Initial set on CONNECT for user {user.id}")
            
            print(f"✅ [RodieConsumer] Connected successfully for user {user.id}")
            # Check for active offer if reconnected during dispatch
            try:
                offer = cache.get(f"active_offer:{user.id}")
                if offer:
                    await self.send_json({
                        "type": "OFFER_REQUEST",
                        "request": offer
                    })
            except Exception:
                pass
        except Exception as e:
            print(f"❌ [RodieConsumer] Connection error: {e}")
            import logging; logging.exception("RodieConsumer connect error")
            await self.close()

    async def disconnect(self, close_code):
        try:
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
            
            # Clean up role and notification groups to prevent stale channel accumulation
            user = self.scope.get("user")
            if user and user.is_authenticated:
                await self.channel_layer.group_discard(f'role_{user.role}', self.channel_name)
                await self.channel_layer.group_discard('notifications', self.channel_name)
                print(f"🔌 [RodieConsumer] {user.username} disconnected - keeping online status as-is")
        except Exception as e:
            import logging; logging.exception("RodieConsumer disconnect error")

    async def send_request(self, event):
        await self.send_json({
            "type": "NEW_REQUEST",
            "data": event["data"]
        })

    async def offer_request(self, event):
        """Standard handler for sequential offers"""
        await self.send_json({
            "type": "OFFER_REQUEST",
            "request": event.get("request")
        })

    async def new_request(self, event):
        """Redundant handler to match some older app versions calling it 'new_request'"""
        await self.send_json({
            "type": "OFFER_REQUEST",
            "request": event.get("request") or event.get("data")
        })

    async def user_status(self, event):
        await self.send_json({
            "type": "USER_STATUS",
            "data": event
        })

    async def chat_message(self, event):
        """Forward chat message to roadie — flat format matching Flutter app expectations"""
        await self.send_json({
            'type': 'CHAT_MESSAGE',
            'request_id': event.get('request_id') or event.get('service_request'),
            'sender_id': event.get('sender_id'),
            'sender_role': event.get('sender_role'),
            'sender_name': event.get('sender_name'),
            'text': event.get('text'),
            'created_at': event.get('created_at'),
        })

    async def chat_notification(self, event):
        """Forward chat notification — skip if sender is this user (prevents echo)"""
        sender_id = event.get('sender_id')
        if sender_id and str(sender_id) == str(self.scope['user'].id):
            return

        await self.send_json({
            'type': 'CHAT_NOTIFICATION',
            'request_id': event.get('request_id') or event.get('service_request'),
            'sender_id': event.get('sender_id'),
            'sender_role': event.get('sender_role'),
            'sender_name': event.get('sender_name'),
            'text': event.get('text'),
            'created_at': event.get('created_at'),
        })

    async def receive_json(self, content):
        # 🟢 HEARTBEAT: Any message from the phone counts as being "Alive"
        try:
            await database_sync_to_async(cache.set)(f"rodie_heartbeat:{self.scope['user'].id}", True, timeout=600)
            # Only print periodically to avoid log spam (every 10th message)
            if getattr(self, '_msg_count', 0) % 10 == 0:
                print(f"💓 [Heartbeat] Updated via message for user {self.scope['user'].id}")
            self._msg_count = getattr(self, '_msg_count', 0) + 1
        except Exception:
            pass

        try:
            msg_type = content.get("type")
            if msg_type == "LOCATION":
                rider_id = content.get("rider_id")
                lat = content.get("lat")
                lng = content.get("lng")
                if lat is not None and lng is not None:
                    # Always cache rodie location for matching
                    try:
                        await cache_set_rodie_location(self.scope['user'].id, lat, lng)
                        # NEW: Update Truly Online heartbeat (10-minute safety window)
                        await database_sync_to_async(cache.set)(f"rodie_heartbeat:{self.scope['user'].id}", True, timeout=600)
                        # Broadcast to all nearby riders
                        await self.broadcast_to_nearby_riders(lat, lng)
                    except Exception:
                        pass
                        
                    # RELIABILITY: If rider_id is missing but roadie is in a ride, find the rider
                    if rider_id is None:
                        try:
                            # Use cache or DB to find if this roadie has an active ride
                            def get_active_rider():
                                req = ServiceRequest.objects.filter(
                                    rodie_id=self.scope['user'].id,
                                    status__in=['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']
                                ).first()
                                return req.rider_id if req else None
                            
                            rider_id = await database_sync_to_async(get_active_rider)()
                        except Exception:
                            pass

                    # Relay to specific rider if during active ride
                    if rider_id is not None:
                        # Calculate distance and ETA for the specific rider
                        distance_km = None
                        eta_seconds = None
                        
                        try:
                            from requests.models import ServiceRequest
                            from locations.models import RodieLocation
                            
                            # Get the active request between this roadie and rider
                            def fetch_active_request():
                                return ServiceRequest.objects.filter(
                                    rodie_id=self.scope['user'].id,
                                    rider_id=rider_id,
                                    status__in=['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']
                                ).first()
                            
                            request = await database_sync_to_async(fetch_active_request)()
                            if request and request.rider_lat and request.rider_lng:
                                # Calculate distance
                                from .utils import calculate_distance_km
                                distance_km = calculate_distance_km(
                                    float(lat), float(lng),
                                    float(request.rider_lat), float(request.rider_lng)
                                )
                                
                                # Estimate ETA (assuming 30 km/h average speed in city)
                                eta_seconds = int((distance_km / 30) * 3600)
                        except Exception as e:
                            print(f"Error calculating ETA: {e}")
                        
                        await self.channel_layer.group_send(
                            f"rider_{rider_id}",
                            {
                                "type": "rodie_location",
                                "lat": lat,
                                "lng": lng,
                                "distance_km": distance_km,
                                "eta_seconds": eta_seconds,
                                "rodie_id": self.scope["user"].id,
                                "rodie_name": self.scope["user"].username,
                            }
                        )
                    await self.channel_layer.group_send(
                        "admin_monitoring",
                        {
                            "type": "rodie_location",
                            "rodie_id": self.scope["user"].id,
                            "lat": lat,
                            "lng": lng
                        }
                    )
            elif msg_type == 'CHAT':
                request_id = content.get('request_id')
                text = content.get('text')
                if request_id and text:
                    user = self.scope['user']
                    sender_name = user.username
                    await database_sync_to_async(ChatMessage.objects.create)(
                        service_request_id=request_id,
                        sender=user,
                        text=text
                    )
                    now_iso = timezone.now().isoformat()
                    # Broadcast to the request room (both parties if joined)
                    await self.channel_layer.group_send(
                        f"request_{request_id}",
                        {
                            'type': 'chat.message',
                            'request_id': request_id,
                            'sender_id': user.id,
                            'sender_role': 'RODIE',
                            'sender_name': sender_name,
                            'text': text,
                            'created_at': now_iso,
                        }
                    )
                    # Also send a notification to the rider's personal channel
                    # so they see a badge even if they haven't joined the request room
                    rider_id = await self._get_rider_id_for_request(request_id)
                    if rider_id:
                        await self.channel_layer.group_send(
                            f"rider_{rider_id}",
                            {
                                'type': 'chat.notification',
                                'request_id': request_id,
                                'sender_id': user.id,
                                'sender_role': 'RODIE',
                                'sender_name': sender_name,
                                'text': text,
                                'created_at': now_iso,
                            }
                        )
            elif msg_type == 'JOIN_REQUEST':
                req_id = content.get('request_id')
                if req_id:
                    await self.channel_layer.group_add(f"request_{req_id}", self.channel_name)
                    # Immediate hydration
                    try:
                        from requests.serializers import ServiceRequestSerializer
                        def get_req_sync(rid):
                            r = ServiceRequest.objects.filter(id=rid).first()
                            return ServiceRequestSerializer(r).data if r else None
                        req_data = await database_sync_to_async(get_req_sync)(req_id)
                        if req_data:
                            await self.send_json({"type": "REQUEST_UPDATE", "status": req_data["status"], "request": req_data})
                    except Exception: pass
                    await self.send_json({"type": "JOIN_SUCCESS", "request_id": req_id})
            elif msg_type == 'PING':
                # Handle keep-alive ping from client
                timestamp = content.get('timestamp')
                # NEW: Update Truly Online heartbeat (10-minute safety window)
                try:
                    await database_sync_to_async(cache.set)(f"rodie_heartbeat:{self.scope['user'].id}", True, timeout=600)
                except Exception:
                    pass
                await self.send_json({"type": "PONG", "timestamp": timestamp})
        except Exception as e:
            print(f"❌ [RodieConsumer] receive_json error: {e}")
            import logging; logging.exception("RodieConsumer receive_json error")

    async def broadcast_to_nearby_riders(self, lat, lng):
        """Broadcast this roadie's location to all nearby riders (within 15km)"""
        try:
            from django.core.cache import cache
            from locations.utils import calculate_distance_km
            from users.models import RiderAvailabilityLog
            
            def get_recent_riders():
                return list(RiderAvailabilityLog.objects.filter(
                    went_offline_at__isnull=True
                ).select_related('user').filter(user__role='RIDER'))
            
            recent_riders = await database_sync_to_async(get_recent_riders)()
            
            for rider_log in recent_riders:
                rider_id = rider_log.user.id
                rider_loc = cache.get(f"rider_loc:{rider_id}")
                if rider_loc:
                    dist = calculate_distance_km(
                        float(rider_loc['lat']), float(rider_loc['lng']),
                        float(lat), float(lng)
                    )
                    if dist <= 15:  # Within 15km
                        await self.channel_layer.group_send(
                            f"rider_{rider_id}",
                            {
                                "type": "rodie_location",
                                "rodie_id": self.scope["user"].id,
                                "lat": lat,
                                "lng": lng,
                                "username": self.scope["user"].username,
                                "service_type": getattr(self.scope["user"], 'service_type', 'TOWING')
                            }
                        )
        except Exception as e:
            print(f"❌ [RodieConsumer] Error broadcasting to nearby riders: {e}")

    @database_sync_to_async
    def _get_rider_id_for_request(self, request_id):
        try:
            req = ServiceRequest.objects.get(id=request_id)
            return req.rider_id
        except ServiceRequest.DoesNotExist:
            return None

    async def request_accepted(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "ACCEPTED", "request": event.get("request")})

    async def request_enroute(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "EN_ROUTE", "request": event.get("request")})

    async def request_started(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "STARTED", "request": event.get("request")})

    async def request_arrived(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "ARRIVED", "request": event.get("request")})

    async def request_completed(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "COMPLETED", "request": event.get("request")})

    async def request_declined(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "DECLINED", "request": event.get("request")})

    async def request_expired(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "EXPIRED", "request": event.get("request")})

    async def request_cancelled(self, event):
        """Handle request cancellation by rider"""
        await self.send_json({
            "type": "REQUEST_CANCELLED",
            "request_id": event.get("request_id"),
            "message": event.get("message", "This request has been cancelled."),
            "reason": event.get("reason"),
            "status": "CANCELLED"
        })
        # Clear any active offer for this roadie if it matches the cancelled request
        try:
            from django.core.cache import cache
            user_id = self.scope['user'].id
            active_offer = cache.get(f"active_offer:{user_id}")
            if active_offer and active_offer.get("id") == event.get("request_id"):
                cache.delete(f"active_offer:{user_id}")
                print(f"🚫 Cleared active offer {event.get('request_id')} for roadie {user_id} due to cancellation")
        except Exception as e:
            print(f"❌ Error clearing active offer for cancelled request: {e}")

    async def rodie_status(self, event):
        await self.send_json({
            "type": "RODIE_STATUS",
            "data": event
        })

    async def account_approved(self, event):
        """Handle account approval notification"""
        await self.send_json({
            'type': 'account.approved',
            'user_id': event.get('user_id'),
            'is_approved': event.get('is_approved'),
            'message': event.get('message')
        })

    async def account_unapproved(self, event):
        """Handle account unapproval notification"""
        await self.send_json({
            'type': 'account.unapproved',
            'user_id': event.get('user_id'),
            'is_approved': event.get('is_approved'),
            'message': event.get('message')
        })

    async def request_proximity(self, event):
        await self.send_json({
            "type": "REQUEST_PROXIMITY",
            "distance_km": event.get("distance_km"),
            "eta_seconds": event.get("eta_seconds")
        })

    async def rider_location(self, event):
        """Relay rider's real-time location to the roadie"""
        await self.send_json({
            "type": "RIDER_LOCATION",
            "lat": event.get("lat"),
            "lng": event.get("lng"),
            "rider_id": event.get("rider_id"),
            "rider_name": event.get("rider_name")
        })


class RiderConsumer(AsyncJsonWebsocketConsumer):

    @database_sync_to_async
    def _log_online(self, user):
        RiderAvailabilityLog.objects.filter(user=user, went_offline_at__isnull=True).update(went_offline_at=timezone.now())
        return RiderAvailabilityLog.objects.create(user=user, went_online_at=timezone.now())

    @database_sync_to_async
    def _log_offline(self, user):
        RiderAvailabilityLog.objects.filter(user=user, went_offline_at__isnull=True).update(went_offline_at=timezone.now())

    @database_sync_to_async
    def _get_nearby_rodies(self, lat, lng):
        """Get nearby roadies visible to riders — only approved, services-selected, online roadies within 15km."""
        from locations.utils import calculate_distance_km
        results = []
        try:
            qs = User.objects.filter(
                role='RODIE',
                is_online=True,
                is_approved=True,
                services_selected=True,
                is_deleted=False,
                is_active=True,
            )

            for u in qs.all():
                # Prefer RodieLocation as the canonical source of truth for rodie position
                try:
                    rl = RodieLocation.objects.get(rodie=u)
                    rodie_lat = rl.lat
                    rodie_lng = rl.lng
                except RodieLocation.DoesNotExist:
                    rodie_lat = getattr(u, 'lat', None)
                    rodie_lng = getattr(u, 'lng', None)

                if rodie_lat is not None and rodie_lng is not None:
                    dist = calculate_distance_km(float(lat), float(lng), float(rodie_lat), float(rodie_lng)) if lat and lng else None
                    if dist is not None and dist > 15:
                        continue
                    results.append({
                        'id': u.id,
                        'username': u.username,
                        'lat': float(rodie_lat),
                        'lng': float(rodie_lng),
                        'distance_km': round(dist, 1) if dist is not None else None,
                    })
        except Exception:
            return []
        return results

    async def connect(self):
        user = self.scope["user"]
        try:
            if not user.is_authenticated:
                print(f"❌ [RiderConsumer] Auth failed - user is AnonymousUser")
                await self.close()
                return
            print(f"🔌 [RiderConsumer] Connection attempt from user {user.id}")
            if user.role != "RIDER":
                print(f"❌ [RiderConsumer] Auth failed - Role: {user.role} (expected RIDER)")
                await self.close()
                return

            # ACCEPT immediately
            await self.accept()

            await self._log_online(user)
            await self.channel_layer.group_send(
                "admin_monitoring",
                {
                    "type": "rider_status",
                    "rider_id": user.id,
                    "is_online": True
                }
            )

            self.group_name = f"rider_{user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.channel_layer.group_add(f'role_{user.role}', self.channel_name)
            await self.channel_layer.group_add('notifications', self.channel_name)

            # --- AUTO-REJOIN ACTIVE REQUESTS ---
            try:
                from requests.models import ServiceRequest
                def get_active_request():
                    return ServiceRequest.objects.filter(
                        rider_id=user.id,
                        status__in=['REQUESTED', 'ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']
                    ).first()
                
                req = await database_sync_to_async(get_active_request)()
                if req:
                    await self.channel_layer.group_add(f"request_{req.id}", self.channel_name)
                    print(f"🔄 [RiderConsumer] Auto-rejoined request group: request_{req.id}")
                    
                    # Send current state immediately to sync UI
                    from requests.serializers import ServiceRequestSerializer
                    serializer_data = await database_sync_to_async(lambda: ServiceRequestSerializer(req).data)()
                    await self.send_json({
                        "type": "REQUEST_UPDATE",
                        "status": req.status,
                        "request": serializer_data
                    })
            except Exception as e:
                print(f"⚠️ [RiderConsumer] Error auto-rejoining active request: {e}")

            print(f"✅ [RiderConsumer] Connected successfully for user {user.id}")
            print(f"✅ [RiderConsumer] Joined groups: {self.group_name}, role_{user.role}, notifications")
            
            # Send nearby roadies on connection
            await self.send_nearby_roadies()
        except Exception as e:
            print(f"❌ [RiderConsumer] Connection error: {e}")
            import logging; logging.exception("RiderConsumer connect error")
            await self.close()

    async def send_nearby_roadies(self):
        """Send nearby roadies to this rider — only when location is known."""
        try:
            from django.core.cache import cache
            rider_loc = cache.get(f"rider_loc:{self.scope['user'].id}")
            if not rider_loc:
                # No cached location — send empty list, rider will get updated on first LOCATION msg
                await self.send_json({"type": "NEARBY_LIST", "roadies": []})
                return
            lat = rider_loc['lat']
            lng = rider_loc['lng']
            nearby = await self._get_nearby_rodies(lat, lng)
            await self.send_json({
                "type": "NEARBY_LIST",
                "roadies": nearby
            })
            print(f"📍 [RiderConsumer] Sent {len(nearby)} nearby roadies to rider {self.scope['user'].id}")
        except Exception as e:
            print(f"❌ [RiderConsumer] Error sending nearby roadies: {e}")

    async def disconnect(self, close_code):
        try:
            user = self.scope.get("user")
            if user and user.is_authenticated:
                await self._log_offline(user)
                await self.channel_layer.group_send(
                    "admin_monitoring",
                    {
                        "type": "rider_status",
                        "rider_id": user.id,
                        "is_online": False
                    }
                )
                # Clean up role and notification groups to prevent stale channel accumulation
                await self.channel_layer.group_discard(f'role_{user.role}', self.channel_name)
                await self.channel_layer.group_discard('notifications', self.channel_name)
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception as e:
            import logging; logging.exception("RiderConsumer disconnect error")

    async def rodie_location(self, event):
        message = {
            "type": "RODIE_LOCATION",
            "lat": event["lat"],
            "lng": event["lng"],
            "rodie_id": event.get("rodie_id"),
            "username": event.get("username", "Roadie"),
            "service_type": event.get("service_type", "TOWING")
        }
        # Only include distance and ETA if they have valid values
        if event.get("distance_km") is not None:
            message["distance_km"] = event["distance_km"]
        if event.get("eta_seconds") is not None:
            message["eta_seconds"] = event["eta_seconds"]
        await self.send_json(message)

    async def request_proximity(self, event):
        """Update the Rider's UI with the distance/ETA of the roadie currently being offered the job."""
        await self.send_json({
            "type": "REQUEST_PROXIMITY",
            "distance_km": event.get("distance_km"),
            "eta_seconds": event.get("eta_seconds")
        })

    async def request_update(self, event):
        await self.send_json({
            "type": "REQUEST_UPDATE",
            "request": event.get("request") or event.get("data"),
            "status": event.get("status")
        })

    async def receive_json(self, content):
        user = self.scope["user"]
        try:
            msg_type = content.get("type")
            if msg_type == "LOCATION":
                lat = content.get("lat")
                lng = content.get("lng")
                if lat is not None and lng is not None:
                    try:
                        await cache_set_rider_location(user.id, lat, lng)
                        # Send nearby roadies after location update
                        await self.send_nearby_roadies()
                        
                        # RELAY: Also relay rider location to the assigned roadie if in an active ride
                        def get_active_rodie():
                            req = ServiceRequest.objects.filter(
                                rider_id=user.id,
                                status__in=['ACCEPTED', 'EN_ROUTE', 'ARRIVED', 'STARTED']
                            ).first()
                            return req.rodie_id if req else None
                        
                        rodie_id = await database_sync_to_async(get_active_rodie)()
                        if rodie_id:
                            await self.channel_layer.group_send(
                                f"rodie_{rodie_id}",
                                {
                                    "type": "rider_location",
                                    "lat": lat,
                                    "lng": lng,
                                    "rider_id": user.id,
                                    "rider_name": user.username
                                }
                            )
                    except Exception:
                        pass

                    await self.channel_layer.group_send(
                        "admin_monitoring",
                        {
                            "type": "rider_location",
                            "rider_id": user.id,
                            "lat": lat,
                            "lng": lng
                        }
                    )
            elif msg_type == 'JOIN_REQUEST':
                req_id = content.get('request_id')
                if req_id:
                    await self.channel_layer.group_add(f"request_{req_id}", self.channel_name)
                    # Immediate hydration
                    try:
                        from requests.serializers import ServiceRequestSerializer
                        def get_req_sync(rid):
                            r = ServiceRequest.objects.filter(id=rid).first()
                            return ServiceRequestSerializer(r).data if r else None
                        req_data = await database_sync_to_async(get_req_sync)(req_id)
                        if req_data:
                            await self.send_json({"type": "REQUEST_UPDATE", "status": req_data["status"], "request": req_data})
                    except Exception: pass
                    await self.send_json({"type": "JOIN_SUCCESS", "request_id": req_id})
            elif msg_type == 'CHAT':
                request_id = content.get('request_id')
                text = content.get('text')
                if request_id and text:
                    user = self.scope['user']
                    sender_name = user.username
                    await database_sync_to_async(ChatMessage.objects.create)(
                        service_request_id=request_id,
                        sender=user,
                        text=text
                    )
                    now_iso = timezone.now().isoformat()
                    # Broadcast to the request room
                    await self.channel_layer.group_send(
                        f"request_{request_id}",
                        {
                            'type': 'chat.message',
                            'request_id': request_id,
                            'sender_id': user.id,
                            'sender_role': 'RIDER',
                            'sender_name': sender_name,
                            'text': text,
                            'created_at': now_iso,
                        }
                    )
                    # Also send notification to the roadie's personal channel
                    rodie_id = await self._get_rodie_id_for_request(request_id)
                    if rodie_id:
                        await self.channel_layer.group_send(
                            f"rodie_{rodie_id}",
                            {
                                'type': 'chat.notification',
                                'request_id': request_id,
                                'sender_id': user.id,
                                'sender_role': 'RIDER',
                                'sender_name': sender_name,
                                'text': text,
                                'created_at': now_iso,
                            }
                        )
            elif msg_type == 'PING':
                # Handle keep-alive ping from client
                timestamp = content.get('timestamp')
                await self.send_json({"type": "PONG", "timestamp": timestamp})
        except Exception as e:
            print(f"❌ [RiderConsumer] receive_json error: {e}")
            import logging; logging.exception("RiderConsumer receive_json error")

    async def notification(self, event):
        await self.send_json({
            'type': 'NOTIFICATION',
            'notification': event.get('notification')
        })

    async def rodie_status(self, event):
        """Relay roadie online/offline toggle to riders so their maps update in real time."""
        await self.send_json({
            "type": "RODIE_STATUS",
            "data": event
        })

    @database_sync_to_async
    def _get_rodie_id_for_request(self, request_id):
        try:
            req = ServiceRequest.objects.get(id=request_id)
            return req.rodie_id
        except ServiceRequest.DoesNotExist:
            return None

    async def chat_message(self, event):
        """Forward chat message to rider — flat format matching Flutter app expectations"""
        await self.send_json({
            'type': 'CHAT_MESSAGE',
            'request_id': event.get('request_id') or event.get('service_request'),
            'sender_id': event.get('sender_id'),
            'sender_role': event.get('sender_role'),
            'sender_name': event.get('sender_name'),
            'text': event.get('text'),
            'created_at': event.get('created_at'),
        })

    async def chat_notification(self, event):
        """Forward chat notification — skip if sender is this user (prevents echo)"""
        sender_id = event.get('sender_id')
        if sender_id and str(sender_id) == str(self.scope['user'].id):
            return

        await self.send_json({
            'type': 'CHAT_NOTIFICATION',
            'request_id': event.get('request_id') or event.get('service_request'),
            'sender_id': event.get('sender_id'),
            'sender_role': event.get('sender_role'),
            'sender_name': event.get('sender_name'),
            'text': event.get('text'),
            'created_at': event.get('created_at'),
        })

    async def request_accepted(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "ACCEPTED", "request": event.get("request")})

    async def request_enroute(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "EN_ROUTE", "request": event.get("request")})

    async def request_started(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "STARTED", "request": event.get("request")})

    async def request_arrived(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "ARRIVED", "request": event.get("request")})

    async def account_approved(self, event):
        await self.send_json({"type": "account.approved", "data": event.get("data")})

    async def account_unapproved(self, event):
        await self.send_json({"type": "account.unapproved", "data": event.get("data")})

    async def request_completed(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "COMPLETED", "request": event.get("request")})

    async def request_expired(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "EXPIRED", "request": event.get("request")})

    async def request_declined(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "DECLINED", "request": event.get("request")})

    async def request_cancelled(self, event):
        """Handle request cancellation confirmation"""
        await self.send_json({
            "type": "REQUEST_CANCELLED",
            "request_id": event.get("request_id"),
            "status": "CANCELLED",
            "message": event.get("message", "This request has been cancelled."),
            "reason": event.get("reason"),
        })

    async def request_proximity(self, event):
        await self.send_json({
            "type": "REQUEST_PROXIMITY",
            "distance_km": event.get("distance_km"),
            "eta_seconds": event.get("eta_seconds")
        })


class AvailabilityConsumer(AsyncJsonWebsocketConsumer):
    """Simple availability consumer.

    Supports two messages from clients:
      - { "type": "GET_NEARBY", "lat": <float>, "lng": <float> }
        -> server responds with { "type": "NEARBY_LIST", "data": [ ... ] }

      - { "type": "LOCATION", "lat": <float>, "lng": <float> }
        -> server will attempt to persist the sender's location (if model fields exist)
           and then respond with an updated nearby list (same payload as GET_NEARBY).
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not getattr(user, 'is_authenticated', False):
            await self.close()
            return

        self.group_name = 'availability'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content):
        typ = content.get('type')
        if typ == 'GET_NEARBY':
            lat = content.get('lat')
            lng = content.get('lng')
            data = await self.get_nearby_rodies(lat, lng)
            await self.send_json({'type': 'NEARBY_LIST', 'data': data})

        elif typ == 'LOCATION':
            lat = content.get('lat')
            lng = content.get('lng')
            try:
                await self.save_user_location(self.scope['user'].id, lat, lng)
            except Exception:
                pass
            data = await self.get_nearby_rodies(lat, lng)
            await self.send_json({'type': 'NEARBY_LIST', 'data': data})

    @database_sync_to_async
    def get_nearby_rodies(self, lat, lng):
        from locations.utils import calculate_distance_km
        results = []
        try:
            qs = User.objects.filter(
                role='RODIE',
                is_online=True,
                is_approved=True,
                services_selected=True,
                is_deleted=False,
                is_active=True,
            )

            for u in qs.all():
                # Prefer RodieLocation as the canonical source of truth for rodie position
                try:
                    rl = RodieLocation.objects.get(rodie=u)
                    rodie_lat = rl.lat
                    rodie_lng = rl.lng
                except RodieLocation.DoesNotExist:
                    rodie_lat = getattr(u, 'lat', None)
                    rodie_lng = getattr(u, 'lng', None)

                if rodie_lat is not None and rodie_lng is not None:
                    dist = calculate_distance_km(float(lat), float(lng), float(rodie_lat), float(rodie_lng)) if lat and lng else None
                    if dist is not None and dist > 15:
                        continue
                    results.append({
                        'rodie_id': u.id,
                        'username': getattr(u, 'username', None),
                        'distance_km': round(dist, 1) if dist is not None else None,
                        'eta_seconds': None,
                        'lat': float(rodie_lat),
                        'lng': float(rodie_lng),
                    })
        except Exception:
            return []
        return results

    async def save_user_location(self, user_id, lat, lng):
        """Save location to cache instead of writing DB on every update.
        Periodic persistence can be implemented separately to flush cache -> DB.
        """
        try:
            # Write ephemeral location into cache to serve realtime components.
            await cache_set_rodie_location(user_id, lat, lng)
        except Exception:
            pass
