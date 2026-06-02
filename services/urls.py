from django.urls import path
from .views import ServiceTypeListView
from .admin_views import (
    ServiceTypeListCreateView,
    ServiceTypeRetrieveUpdateDestroyView,
    RodieServiceListCreateView,
    RodieServiceRetrieveUpdateDestroyView,
    ServiceSubCategoryListCreateView,
    ServiceSubCategoryRetrieveUpdateDestroyView,
)

urlpatterns = [
    # Public app endpoint (used by both apps)
    path('', ServiceTypeListView.as_view(), name='service-list'),

    # Admin service type CRUD
    path('admin/', ServiceTypeListCreateView.as_view(), name='admin-service-list'),
    path('admin/<int:pk>/', ServiceTypeRetrieveUpdateDestroyView.as_view(), name='admin-service-detail'),

    # Roadie services
    path('admin/rodie-services/', RodieServiceListCreateView.as_view(), name='admin-rodie-service-list'),
    path('admin/rodie-services/<int:pk>/', RodieServiceRetrieveUpdateDestroyView.as_view(), name='admin-rodie-service-detail'),

    # Subcategories
    path('admin/subcategories/', ServiceSubCategoryListCreateView.as_view(), name='admin-subcategory-list'),
    path('admin/subcategories/<int:pk>/', ServiceSubCategoryRetrieveUpdateDestroyView.as_view(), name='admin-subcategory-detail'),
]
