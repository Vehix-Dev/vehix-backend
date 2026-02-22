from django.urls import path
from .views import ServiceTypeListView

urlpatterns = [
    path('', ServiceTypeListView.as_view(), name='service-list'),
]
