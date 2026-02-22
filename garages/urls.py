from django.urls import path
from .views import (
    GarageRegistrationView, GarageListView, GarageDetailView,
    GarageServiceRequestCreateView, RiderGarageRequestsView, GarageRequestsView,
    AdminGarageListView, AdminGarageDetailView, AdminGarageVerificationView,
    AdminGarageStatsView
)

app_name = 'garages'

urlpatterns = [
    # Public endpoints for garage partners
    path('register/', GarageRegistrationView.as_view(), name='garage_register'),

    # Endpoints for riders
    path('', GarageListView.as_view(), name='garage_list'),
    path('<int:pk>/', GarageDetailView.as_view(), name='garage_detail'),
    path('<int:pk>/request/', GarageServiceRequestCreateView.as_view(), name='garage_service_request'),
    path('requests/', RiderGarageRequestsView.as_view(), name='rider_garage_requests'),

    # Endpoints for garages (future implementation)
    path('garage/requests/', GarageRequestsView.as_view(), name='garage_requests'),

    # Admin endpoints
    path('admin/', AdminGarageListView.as_view(), name='admin_garage_list'),
    path('admin/<int:pk>/', AdminGarageDetailView.as_view(), name='admin_garage_detail'),
    path('admin/<int:pk>/verify/', AdminGarageVerificationView.as_view(), name='admin_garage_verify'),
    path('admin/stats/', AdminGarageStatsView.as_view(), name='admin_garage_stats'),
]
