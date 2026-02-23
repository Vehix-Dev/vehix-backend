from rest_framework import generics, permissions, filters, parsers
from .models import ServiceType, RodieService
from .admin_serializers import ServiceTypeSerializer, RodieServiceSerializer


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
