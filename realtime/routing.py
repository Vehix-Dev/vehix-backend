from django.urls import re_path
from .consumers import RodieConsumer, RiderConsumer, AvailabilityConsumer, AdminConsumer

websocket_urlpatterns = [
    re_path(r'^ws/roadie/$', RodieConsumer.as_asgi()),
    re_path(r'^ws/rodie/$', RodieConsumer.as_asgi()),  # Legacy support
    re_path(r'^ws/rider/$', RiderConsumer.as_asgi()),
    re_path(r'^ws/admin/$', AdminConsumer.as_asgi()),
    re_path(r'^ws/availability/$', AvailabilityConsumer.as_asgi()),
    re_path(r'^ws/request/(?P<request_id>\d+)/$', RodieConsumer.as_asgi()),
]
