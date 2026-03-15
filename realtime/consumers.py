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
        # Update User model for fallback
        User.objects.filter(id=user_id).update(lat=lat_f, lng=lng_f)
        # CRITICAL: Update RodieLocation table for find_nearby_rodies matching
        from locations.models import RodieLocation
        RodieLocation.objects.update_or_create(
            rodie_id=user_id,
            defaults={'lat': lat_f, 'lng': lng_f, 'updated_at': timezone.now()}
        )
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

            self.group_name = f"rodie_{user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.channel_layer.group_add(f'role_{user.role}', self.channel_name)
            await self.channel_layer.group_add('notifications', self.channel_name)
            await self._set_online(user, True)
            await self.accept()
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
            
            # FIXED: Don't automatically set roadie offline on disconnect
            # Roadies should only go offline when they explicitly toggle the switch
            user = self.scope.get("user")
            if user and user.is_authenticated:
                print(f"🔌 [RodieConsumer] {user.username} disconnected - keeping online status as-is")
        except Exception as e:
            import logging; logging.exception("RodieConsumer disconnect error")

    async def send_request(self, event):
        await self.send_json({
            "type": "NEW_REQUEST",
            "data": event["data"]
        })

    async def offer_request(self, event):
        await self.send_json({
            "type": "OFFER_REQUEST",
            "request": event.get("request")
        })

    async def user_status(self, event):
        await self.send_json({
            "type": "USER_STATUS",
            "data": event
        })

    async def notification(self, event):
        await self.send_json({
            'type': 'NOTIFICATION',
            'notification': event.get('notification')
        })

    async def request_update(self, event):
        await self.send_json({
            "type": "REQUEST_UPDATE",
            "request": event.get("request") or event.get("data")
        })

    async def receive_json(self, content):
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
                    except Exception:
                        pass
                    # Relay to specific rider if during active ride
                    if rider_id is not None:
                        await self.channel_layer.group_send(
                            f"rider_{rider_id}",
                            {
                                "type": "rodie_location",
                                "lat": lat,
                                "lng": lng
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
                    await database_sync_to_async(ChatMessage.objects.create)(
                        service_request_id=request_id,
                        sender=self.scope['user'],
                        text=text
                    )
                    await self.channel_layer.group_send(
                        f"request_{request_id}",
                        {
                            'type': 'chat.message',
                            'sender_id': self.scope['user'].id,
                            'sender_role': 'RODIE',
                            'text': text,
                            'created_at': timezone.now().isoformat(),
                        }
                    )
            elif msg_type == 'JOIN_REQUEST':
                req_id = content.get('request_id')
                if req_id:
                    await self.channel_layer.group_add(f"request_{req_id}", self.channel_name)
                    await self.send_json({"type": "JOIN_SUCCESS", "request_id": req_id})
            elif msg_type == 'PING':
                # Handle keep-alive ping from client
                await self.send_json({"type": "PONG"})
        except Exception as e:
            print(f"❌ [RodieConsumer] receive_json error: {e}")
            import logging; logging.exception("RodieConsumer receive_json error")

    async def chat_message(self, event):
        await self.send_json({
            'type': 'CHAT_MESSAGE',
            'sender_id': event.get('sender_id'),
            'sender_role': event.get('sender_role'),
            'text': event.get('text'),
            'created_at': event.get('created_at'),
        })

    async def request_accepted(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "ACCEPTED", "request": event.get("request")})

    async def request_enroute(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "EN_ROUTE", "request": event.get("request")})

    async def request_started(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "STARTED", "request": event.get("request")})

    async def request_completed(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "COMPLETED", "request": event.get("request")})

    async def request_declined(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "DECLINED", "request": event.get("request")})

    async def request_expired(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "EXPIRED", "request": event.get("request")})

    async def rodie_status(self, event):
        await self.send_json({
            "type": "RODIE_STATUS",
            "data": event
        })


class RiderConsumer(AsyncJsonWebsocketConsumer):

    @database_sync_to_async
    def _log_online(self, user):
        RiderAvailabilityLog.objects.filter(user=user, went_offline_at__isnull=True).update(went_offline_at=timezone.now())
        return RiderAvailabilityLog.objects.create(user=user, went_online_at=timezone.now())

    @database_sync_to_async
    def _log_offline(self, user):
        RiderAvailabilityLog.objects.filter(user=user, went_offline_at__isnull=True).update(went_offline_at=timezone.now())

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
            await self.accept()
            print(f"✅ [RiderConsumer] Connected successfully for user {user.id}")
            print(f"✅ [RiderConsumer] Joined groups: {self.group_name}, role_{user.role}, notifications")
        except Exception as e:
            print(f"❌ [RiderConsumer] Connection error: {e}")
            import logging; logging.exception("RiderConsumer connect error")
            await self.close()

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
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception as e:
            import logging; logging.exception("RiderConsumer disconnect error")

    async def rodie_location(self, event):
        await self.send_json({
            "type": "RODIE_LOCATION",
            "lat": event["lat"],
            "lng": event["lng"]
        })

    async def request_update(self, event):
        await self.send_json({
            "type": "REQUEST_UPDATE",
            "request": event.get("request") or event.get("data")
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
                    await self.send_json({"type": "JOIN_SUCCESS", "request_id": req_id})
            elif msg_type == 'CHAT':
                request_id = content.get('request_id')
                text = content.get('text')
                if request_id and text:
                    await database_sync_to_async(ChatMessage.objects.create)(
                        service_request_id=request_id,
                        sender=self.scope['user'],
                        text=text
                    )
                    await self.channel_layer.group_send(
                        f"request_{request_id}",
                        {
                            'type': 'chat.message',
                            'sender_id': self.scope['user'].id,
                            'sender_role': 'RIDER',
                            'text': text,
                            'created_at': timezone.now().isoformat(),
                        }
                    )
            elif msg_type == 'PING':
                # Handle keep-alive ping from client
                await self.send_json({"type": "PONG"})
        except Exception as e:
            print(f"❌ [RiderConsumer] receive_json error: {e}")
            import logging; logging.exception("RiderConsumer receive_json error")

    async def notification(self, event):
        await self.send_json({
            'type': 'NOTIFICATION',
            'notification': event.get('notification')
        })

    async def rodie_status(self, event):
        await self.send_json({
            "type": "RODIE_STATUS",
            "data": event
        })

    async def chat_message(self, event):
        await self.send_json({
            'type': 'CHAT_MESSAGE',
            'sender_id': event.get('sender_id'),
            'sender_role': event.get('sender_role'),
            'text': event.get('text'),
            'created_at': event.get('created_at'),
        })

    async def request_accepted(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "ACCEPTED", "request": event.get("request")})

    async def request_enroute(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "EN_ROUTE", "request": event.get("request")})

    async def request_started(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "STARTED", "request": event.get("request")})

    async def request_completed(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "COMPLETED", "request": event.get("request")})

    async def request_expired(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "EXPIRED", "request": event.get("request")})

    async def request_declined(self, event):
        await self.send_json({"type": "REQUEST_UPDATE", "status": "DECLINED", "request": event.get("request")})

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
        results = []
        try:
            qs = User.objects.filter(role='RODIE')
            try:
                qs = qs.filter(is_online=True)
            except Exception:
                pass

            for u in qs.all():
                # Prefer RodieLocation as the canonical source of truth for rodie position
                try:
                    rl = RodieLocation.objects.get(rodie=u)
                    rodie_lat = rl.lat
                    rodie_lng = rl.lng
                except RodieLocation.DoesNotExist:
                    rodie_lat = getattr(u, 'lat', None) or getattr(u, 'last_lat', None) or getattr(u, 'current_lat', None)
                    rodie_lng = getattr(u, 'lng', None) or getattr(u, 'last_lng', None) or getattr(u, 'current_lng', None)

                results.append({
                    'rodie_id': u.id,
                    'username': getattr(u, 'username', None),
                    'distance_meters': None,
                    'eta_seconds': None,
                    'lat': rodie_lat,
                    'lng': rodie_lng,
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
