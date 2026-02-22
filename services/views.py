from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.contrib.auth import get_user_model
from .models import ServiceType, RodieService

User = get_user_model()


class RodieMyServicesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('RODIE', 'MECHANIC'):
            return Response({'error': 'Only roadies and mechanics may manage services'}, status=status.HTTP_403_FORBIDDEN)
        services = RodieService.objects.filter(rodie=request.user).select_related('service')
        return Response([{'id': s.id, 'service_id': s.service.id, 'service_name': s.service.name} for s in services])

    def post(self, request):
        if request.user.role != 'RODIE':
            return Response({'error': 'Only roadies may manage services'}, status=status.HTTP_403_FORBIDDEN)
        service_ids = request.data.get('service_ids')
        if not isinstance(service_ids, list):
            return Response({'error': 'service_ids must be a list of ids'}, status=status.HTTP_400_BAD_REQUEST)
        existing = RodieService.objects.filter(rodie=request.user)
        existing_service_ids = set(existing.values_list('service_id', flat=True))
        desired = set()
        for i in service_ids:
            try:
                desired.add(int(i))
            except Exception:
                continue
        to_delete = existing.filter(service_id__in=(existing_service_ids - desired))
        to_delete.delete()
        for sid in (desired - existing_service_ids):
            try:
                svc = ServiceType.objects.get(id=sid)
                RodieService.objects.create(rodie=request.user, service=svc)
            except ServiceType.DoesNotExist:
                continue
        services = RodieService.objects.filter(rodie=request.user).select_related('service')
        return Response([{'service_id': s.service.id, 'service_name': s.service.name} for s in services])


from rest_framework import generics
from .serializers import ServiceTypeSerializer

class ServiceTypeListView(generics.ListAPIView):
    """
    List all active service types available for riders.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ServiceTypeSerializer
    pagination_class = None

    def get_queryset(self):
        return ServiceType.objects.filter(is_active=True).order_by('name')
