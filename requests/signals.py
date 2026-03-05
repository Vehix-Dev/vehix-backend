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
    1. New request: all rodies that offer the requested service + are online + are nearby
    2. Assigned rodie: request updates
    3. Rider: request updates
    4. Admin: monitoring updates
    """
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    from requests.serializers import ServiceRequestSerializer
    from requests.services import find_nearby_rodies

    data = ServiceRequestSerializer(instance).data

    print(f"\n🔔 SIGNAL FIRED: Request {instance.id} created={created}, status={instance.status}, rodie_id={instance.rodie_id}")

    # If request is newly created and REQUESTED, find matching rodies and send offers
    if created and instance.status == 'REQUESTED':
        print(f"🔍 Finding nearby rodies for service: {instance.service_type.name}")
        nearby_rodies = find_nearby_rodies(
            instance.service_type,
            float(instance.rider_lat),
            float(instance.rider_lng)
        )
        print(f"📡 Found {len(nearby_rodies)} matching rodies:")
        for item in nearby_rodies:
            rodie = item.get('rodie')
            print(f"   💬 Sending to {rodie.username} ({item['distance']:.2f}km away)")
            try:
                async_to_sync(channel_layer.group_send)(
                    f"rodie_{rodie.id}",
                    {
                        "type": "send_request",
                        "data": data
                    }
                )
            except Exception as e:
                print(f"   ❌ Error sending to {rodie.username}: {e}")
    
    # If request is assigned to a specific rodie, send update
    if instance.rodie_id:
        print(f"✅ Sending update to assigned rodie {instance.rodie_id}")
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
    print(f"✨ Signal complete for request {instance.id}\n")