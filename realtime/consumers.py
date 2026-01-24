from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

from requests.models import ServiceRequest
from requests.models_chat import ChatMessage
from users.models import RiderAvailabilityLog
from django.utils import timezone
User = get_user_model()

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

    async def connect(self):
        user = self.scope["user"]
        try:
            if not user.is_authenticated or user.role != "RODIE":
                await self.close()
                return

            self.group_name = f"rodie_{user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.channel_layer.group_add(f'role_{user.role}', self.channel_name)
            await self.channel_layer.group_add('notifications', self.channel_name)
            await self.accept()
        except Exception as e:
            import logging; logging.exception("RodieConsumer connect error")
            await self.close()

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
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
            "data": event.get("data")
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
            "data": event["data"]
        })

    async def receive_json(self, content):
        try:
            msg_type = content.get("type")
            if msg_type == "LOCATION":
                rider_id = content.get("rider_id")
                lat = content.get("lat")
                lng = content.get("lng")
                if rider_id is not None and lat is not None and lng is not None:
                    # Only send if data is valid
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
                            'text': text,
                            'created_at': None,
                        }
                    )
        except Exception as e:
            import logging; logging.exception("RodieConsumer receive_json error")


class RiderConsumer(AsyncJsonWebsocketConsumer):

    @database_sync_to_async
    def _log_online(self, user):
        # End any previous open session
        RiderAvailabilityLog.objects.filter(user=user, went_offline_at__isnull=True).update(went_offline_at=timezone.now())
        # Start new session
        return RiderAvailabilityLog.objects.create(user=user, went_online_at=timezone.now())

    @database_sync_to_async
    def _log_offline(self, user):
        RiderAvailabilityLog.objects.filter(user=user, went_offline_at__isnull=True).update(went_offline_at=timezone.now())

    async def connect(self):
        user = self.scope["user"]
        try:
            if not user.is_authenticated or user.role != "RIDER":
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
        except Exception as e:
            import logging; logging.exception("RiderConsumer connect error")
            await self.close()

    async def disconnect(self, close_code):
        user = self.scope["user"]
        try:
            if user.is_authenticated:
                await self._log_offline(user)
                await self.channel_layer.group_send(
                    "admin_monitoring",
                    {
                        "type": "rider_status",
                        "rider_id": user.id,
                        "is_online": False
                    }
                )
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
            "data": event["data"]
        })

    async def receive_json(self, content):
        user = self.scope["user"]
        try:
            msg_type = content.get("type")
            if msg_type == "LOCATION":
                lat = content.get("lat")
                lng = content.get("lng")
                if lat is not None and lng is not None:
                    # No DB write for live location, just broadcast
                    await self.channel_layer.group_send(
                        "admin_monitoring",
                        {
                            "type": "rider_location",
                            "rider_id": user.id,
                            "lat": lat,
                            "lng": lng
                        }
                    )
        except Exception as e:
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
            'text': event.get('text'),
            'created_at': event.get('created_at'),
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

    @database_sync_to_async
    def save_user_location(self, user_id, lat, lng):
        try:
            user = User.objects.get(id=user_id)
        except Exception:
            return

        updated_fields = []
        if hasattr(user, 'lat') and hasattr(user, 'lng'):
            try:
                user.lat = lat
                user.lng = lng
                updated_fields += ['lat', 'lng']
            except Exception:
                pass
        elif hasattr(user, 'last_lat') and hasattr(user, 'last_lng'):
            try:
                user.last_lat = lat
                user.last_lng = lng
                updated_fields += ['last_lat', 'last_lng']
            except Exception:
                pass
        elif hasattr(user, 'current_lat') and hasattr(user, 'current_lng'):
            try:
                user.current_lat = lat
                user.current_lng = lng
                updated_fields += ['current_lat', 'current_lng']
            except Exception:
                pass

        if updated_fields:
            try:
                user.save(update_fields=updated_fields)
            except Exception:
                pass
