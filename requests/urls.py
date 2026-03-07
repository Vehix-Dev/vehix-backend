from django.urls import path
from .views import (
    CreateServiceRequestView,
    ChatMessageCreateAPIView,
    AcceptRequestView,
    DeclineRequestView,
    CancelRequestView,
    EnrouteRequestView,
    StartRequestView,
    CompleteRequestView,
    RiderRequestsListView,
    RoadieRequestsListView,
    NearbyRodieListView,
    RateServiceRequestView,
)

urlpatterns = [
    path('create/', CreateServiceRequestView.as_view()),
    path('my/', RiderRequestsListView.as_view(), name='rider_my_requests'),
    path('roadie/', RoadieRequestsListView.as_view(), name='roadie_requests'),
    path('<int:pk>/chat/', ChatMessageCreateAPIView.as_view(), name='request_chat_create'),
    path('<int:pk>/accept/', AcceptRequestView.as_view(), name='request_accept'),
    path('<int:pk>/decline/', DeclineRequestView.as_view(), name='request_decline'),
    path('<int:pk>/cancel/', CancelRequestView.as_view(), name='request_cancel'),
    path('<int:pk>/enroute/', EnrouteRequestView.as_view(), name='request_enroute'),
    path('<int:pk>/start/', StartRequestView.as_view(), name='request_start'),
    path('<int:pk>/complete/', CompleteRequestView.as_view(), name='request_complete'),
    path('<int:pk>/rate/', RateServiceRequestView.as_view(), name='request_rate'),
    path('nearby/', NearbyRodieListView.as_view(), name='nearby_rodies'),
]
