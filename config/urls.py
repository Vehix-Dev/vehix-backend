from django.contrib import admin
import sys
import os

# CRITICAL: Deep purge 'requests' from module cache and prioritize local path.
# This prevents the system library from shadowing the local Django 'requests' app.
_old_path = sys.path[:]
_old_mods = {k: v for k, v in sys.modules.items() if k == 'requests' or k.startswith('requests.')}
try:
    if '' not in sys.path: sys.path.insert(0, '')
    for mod_name in list(_old_mods.keys()):
        del sys.modules[mod_name]
    
    from django.urls import path, include
finally:
    sys.path[:] = _old_path
    sys.modules.update(_old_mods)
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="Vehix API",
      default_version='v1',
      description="API documentation for Vehix Backend",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@vehix.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('users.urls')),
    path('api/requests/', include('requests.urls')),
    path('api/services/', include('services.urls')),
    path('api/images/', include('images.urls')),
    path('api/garages/', include('garages.urls')),
    path('api/swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('api/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Force reload trigger 2