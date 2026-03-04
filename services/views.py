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
        return Response({
            'services': [{'id': s.id, 'service_id': s.service.id, 'service_name': s.service.name} for s in services],
            'services_selected': request.user.services_selected
        })

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
        
        # Mark services as selected
        if not request.user.services_selected:
            request.user.services_selected = True
            request.user.save(update_fields=['services_selected'])
        
        services = RodieService.objects.filter(rodie=request.user).select_related('service')
        return Response({
            'success': True,
            'message': 'Services updated successfully',
            'services': [{'service_id': s.service.id, 'service_name': s.service.name} for s in services],
            'services_selected': request.user.services_selected
        })


class RodieInitialServiceSelectionView(APIView):
    """
    First-time service selection for roadies after registration/login
    POST: Select services for first time
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'RODIE':
            return Response(
                {'error': 'Only roadies can select services'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if request.user.services_selected:
            return Response({
                'message': 'Services already selected. Use Manage My Services to update.',
            }, status=status.HTTP_200_OK)
        
        service_ids = request.data.get('service_ids', [])
        if not isinstance(service_ids, list):
            return Response(
                {'error': 'service_ids must be a list of integers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not service_ids:
            return Response(
                {'error': 'Please select at least one service'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create service selections
        created_count = 0
        for service_id in service_ids:
            try:
                svc = ServiceType.objects.get(id=int(service_id), is_active=True)
                RodieService.objects.get_or_create(rodie=request.user, service=svc)
                created_count += 1
            except (ServiceType.DoesNotExist, ValueError):
                continue
        
        if created_count == 0:
            return Response(
                {'error': 'No valid services found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark services as selected
        request.user.services_selected = True
        request.user.save(update_fields=['services_selected'])
        
        # Return selected services
        services = RodieService.objects.filter(rodie=request.user).select_related('service')
        return Response({
            'success': True,
            'message': 'Services selected successfully',
            'services': [
                {
                    'service_id': s.service.id,
                    'service_name': s.service.name,
                    'fixed_price': str(s.service.fixed_price),
                    'code': s.service.code,
                    'category': s.service.category
                } for s in services
            ],
            'services_selected': True
        }, status=status.HTTP_201_CREATED)


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
