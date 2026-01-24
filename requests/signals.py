from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import ServiceRequest


@receiver(post_save, sender=ServiceRequest)
def broadcast_request_update(sender, instance, created, **kwargs):
    """
    Triggers whenever a ServiceRequest is saved (created or updated).
    Broadcasts the update to:
    1. The assigned Rider
    2. The assigned Roadie (if any)
    3. The Admin monitoring group
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    from requests.serializers import ServiceRequestSerializer

    data = ServiceRequestSerializer(instance).data

    event_message = {
        "type": "request_update",  
        "data": data
    }

    if instance.rider_id:
        async_to_sync(channel_layer.group_send)(f"rider_{instance.rider_id}", event_message)

    if instance.rodie_id:
        async_to_sync(channel_layer.group_send)(f"rodie_{instance.rodie_id}", event_message) 
    async_to_sync(channel_layer.group_send)("admin_monitoring", event_message)