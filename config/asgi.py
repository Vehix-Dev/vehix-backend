import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Setup Django first before importing models
django.setup()

# CRITICAL: Deep purge 'requests' from module cache to prevent shadowing.
import sys
_old_mods = {k: v for k, v in sys.modules.items() if k == 'requests' or k.startswith('requests.')}
for mod_name in list(_old_mods.keys()):
    del sys.modules[mod_name]

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from users.middleware import JwtAuthMiddleware
import realtime.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JwtAuthMiddleware(
        URLRouter(
            realtime.routing.websocket_urlpatterns
        )
    ),
})
