from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Garage, GarageServiceRequest
from .serializers import (
    GarageRegistrationSerializer, GarageListSerializer, GarageDetailSerializer,
    GarageServiceRequestSerializer, GarageAdminSerializer
)
from django.contrib.auth import get_user_model

User = get_user_model()


class GarageRegistrationView(generics.CreateAPIView):
    """View for garage partners to register their business"""
    serializer_class = GarageRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        # Capture registration metadata
        request = self.request
        serializer.save(
            registration_ip=request.META.get('REMOTE_ADDR'),
            device_type=request.META.get('HTTP_USER_AGENT', '')[:50],
            terms_accepted_at=timezone.now(),
            terms_accepted_ip=request.META.get('REMOTE_ADDR')
        )


class GarageListView(generics.ListAPIView):
    """View for riders to browse verified garages"""
    serializer_class = GarageListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Garage.objects.filter(verification_status='VERIFIED')


class GarageDetailView(generics.RetrieveAPIView):
    """View for detailed garage information"""
    serializer_class = GarageDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Garage.objects.filter(verification_status='VERIFIED')


class GarageServiceRequestCreateView(generics.CreateAPIView):
    """View for riders to request services from garages"""
    serializer_class = GarageServiceRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(rider=self.request.user)


class RiderGarageRequestsView(generics.ListAPIView):
    """View for riders to see their garage service requests"""
    serializer_class = GarageServiceRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GarageServiceRequest.objects.filter(rider=self.request.user).order_by('-created_at')


class GarageRequestsView(generics.ListAPIView):
    """View for garages to see their service requests (future implementation)"""
    serializer_class = GarageServiceRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # This would be implemented when garage owners have accounts
        # For now, return empty queryset
        return GarageServiceRequest.objects.none()


# Admin Views
class AdminGarageListView(generics.ListCreateAPIView):
    """Admin view to list and create garages"""
    serializer_class = GarageAdminSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_staff:
            return Garage.objects.none()
        return Garage.objects.all().order_by('-registration_date')

    def perform_create(self, serializer):
        serializer.save()


class AdminGarageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin view to manage individual garages"""
    serializer_class = GarageAdminSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_staff:
            return Garage.objects.none()
        return Garage.objects.all()


class AdminGarageVerificationView(APIView):
    """Admin view to verify/reject/suspend garages"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        garage = get_object_or_404(Garage, pk=pk)
        action = request.data.get('action')
        reason = request.data.get('reason', '')

        if action == 'verify':
            garage.verification_status = 'VERIFIED'
            garage.verified_by = request.user
            garage.verified_at = timezone.now()
        elif action == 'reject':
            garage.verification_status = 'REJECTED'
            garage.rejection_reason = reason
            garage.verified_by = request.user
            garage.verified_at = timezone.now()
        elif action == 'suspend':
            garage.verification_status = 'SUSPENDED'
            garage.suspension_reason = reason
            garage.verified_by = request.user
            garage.verified_at = timezone.now()
        else:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

        garage.save()
        return Response({'status': f'Garage {action}ed successfully'})


class AdminGarageStatsView(APIView):
    """Admin view for garage statistics"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        stats = {
            'total_garages': Garage.objects.count(),
            'verified_garages': Garage.objects.filter(verification_status='VERIFIED').count(),
            'pending_garages': Garage.objects.filter(verification_status='SUBMITTED').count(),
            'under_review': Garage.objects.filter(verification_status='UNDER_REVIEW').count(),
            'rejected_garages': Garage.objects.filter(verification_status='REJECTED').count(),
            'suspended_garages': Garage.objects.filter(verification_status='SUSPENDED').count(),
        }
        return Response(stats)
