from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import ServiceRequest


@receiver(post_save, sender=ServiceRequest)
def broadcast_request_update(sender, instance, created, **kwargs):
    """
    Triggers whenever a ServiceRequest is saved (created or updated).
    Only broadcasts for non-terminal statuses — the views handle
    CANCELLED / COMPLETED / EXPIRED notifications explicitly to avoid
    duplicate or ghost messages.
    """
    # Skip terminal statuses — views send targeted notifications for these
    if instance.status in ('CANCELLED', 'COMPLETED', 'EXPIRED'):
        print(f" SIGNAL SKIPPED: Request {instance.id} status={instance.status} (terminal — views handle this)")
        return

    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    from requests.serializers import ServiceRequestSerializer

    data = ServiceRequestSerializer(instance).data

    print(f"\n SIGNAL FIRED: Request {instance.id} created={created}, status={instance.status}, rodie_id={instance.rodie_id}")

    # If request is assigned to a specific rodie, send update
    if instance.rodie_id:
        print(f" Sending update to assigned rodie {instance.rodie_id}")
        async_to_sync(channel_layer.group_send)(
            f"rodie_{instance.rodie_id}", 
            {
                "type": "request_update",
                "data": data
            }
        )
    
    # Update to rider
    if instance.rider_id:
        async_to_sync(channel_layer.group_send)(
            f"rider_{instance.rider_id}", 
            {
                "type": "request_update",
                "data": data
            }
        )
    
    # Update to admin monitoring
    async_to_sync(channel_layer.group_send)(
        "admin_monitoring", 
        {
            "type": "request_update",
            "data": data
        }
    )
    print(f" Signal complete for request {instance.id}\n")