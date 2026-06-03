from rest_framework import generics, permissions, filters, parsers
from .models import ServiceType, RodieService, ServiceSubCategory
from .admin_serializers import ServiceTypeSerializer, RodieServiceSerializer, ServiceSubCategorySerializer


class ServiceTypeListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = ServiceTypeSerializer
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['code', 'name']

    def get_queryset(self):
        return ServiceType.objects.all()


class ServiceTypeRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ServiceTypeSerializer
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        return ServiceType.objects.all()


class RodieServiceListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RodieServiceSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['rodie__username']

    def get_queryset(self):
        return RodieService.objects.select_related('rodie', 'service').all()


class RodieServiceRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RodieServiceSerializer

    def get_queryset(self):
        return RodieService.objects.select_related('rodie', 'service').all()


class ServiceSubCategoryListCreateView(generics.ListCreateAPIView):
    """List and create subcategories for a service. Optionally filter by service_id query param."""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    serializer_class = ServiceSubCategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        qs = ServiceSubCategory.objects.select_related('service').all()
        service_id = self.request.query_params.get('service_id')
        if service_id:
            qs = qs.filter(service_id=service_id)
        return qs


class ServiceSubCategoryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ServiceSubCategorySerializer

    def get_queryset(self):
        return ServiceSubCategory.objects.select_related('service').all()
