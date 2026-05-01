from rest_framework import generics, viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg, Count

from .models import RequestCancellation, CancellationReason, ServiceRequest
from .models_rating import Rating
from .cancellation_serializers import RequestCancellationSerializer, CancellationReasonSerializer


class CancellationReasonViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing cancellation reasons
    Admins can CRUD cancellation reasons
    Users can only view their applicable reasons
    """
    serializer_class = CancellationReasonSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['role', 'is_active']
    ordering_fields = ['order', 'role']
    ordering = ['role', 'order']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'ADMIN':
            return CancellationReason.objects.all()
        # Regular users only see reasons for their role
        return CancellationReason.objects.filter(role=user.role, is_active=True)
    
    def get_permissions(self):
        """Only admins can create/update/delete reasons"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return super().get_permissions()


class RequestCancellationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing request cancellations
    Users can view their own cancellations
    Admins can view all
    """
    serializer_class = RequestCancellationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['cancelled_by__role', 'reason__role']
    ordering_fields = ['cancelled_at']
    ordering = ['-cancelled_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'ADMIN':
            return RequestCancellation.objects.all().select_related(
                'request', 'cancelled_by', 'reason'
            )
        # Users can only see cancellations they made
        return RequestCancellation.objects.filter(
            cancelled_by=user
        ).select_related('request', 'cancelled_by', 'reason')


class RatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ratings and reviews
    Users can create ratings after service completion
    Admins can view all ratings
    """
    serializer_class = None  # Will be defined per action
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['service_request__status', 'created_at']
    ordering_fields = ['created_at', 'rating']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'ADMIN':
            return Rating.objects.all().select_related(
                'service_request', 'rater', 'rated_user'
            )
        # Users can see ratings for their requests
        return Rating.objects.filter(
            Q(rater=user) | Q(rated_user=user)
        ).select_related('service_request', 'rater', 'rated_user')
    
    def get_serializer_class(self):
        from .models_rating import Rating as RatingModel
        
        class RatingSerializer(serializers.ModelSerializer):
            rater_username = serializers.CharField(source='rater.username', read_only=True)
            rated_user_username = serializers.CharField(source='rated_user.username', read_only=True)
            service_request_id = serializers.IntegerField(source='service_request.id', read_only=True)
            
            class Meta:
                model = RatingModel
                fields = (
                    'id', 'service_request', 'service_request_id', 'rater', 'rater_username',
                    'rated_user', 'rated_user_username', 'rating', 'comment',
                    'created_at', 'updated_at'
                )
                read_only_fields = ('created_at', 'updated_at')
        
        return RatingSerializer
    
    def perform_create(self, serializer):
        # Set the rater to the current user
        serializer.save(rater=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_ratings(self, request):
        """Get ratings submitted by the current user"""
        ratings = self.get_queryset().filter(rater=request.user)
        serializer = self.get_serializer(ratings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def ratings_about_me(self, request):
        """Get ratings about the current user"""
        ratings = self.get_queryset().filter(rated_user=request.user)
        
        # Include aggregate stats
        stats = ratings.aggregate(
            average_rating=Avg('rating'),
            total_ratings=Count('id')
        )
        
        serializer = self.get_serializer(ratings, many=True)
        return Response({
            'statistics': stats,
            'ratings': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def request_ratings(self, request):
        """Get all ratings for a specific request"""
        request_id = request.query_params.get('request_id')
        if not request_id:
            return Response(
                {'detail': 'request_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service_request = ServiceRequest.objects.get(id=int(request_id))
        except ServiceRequest.DoesNotExist:
            return Response(
                {'detail': 'Request not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission
        if not (request.user.is_staff or request.user.role == 'ADMIN' or 
                request.user in [service_request.rider, service_request.rodie]):
            return Response(
                {'detail': 'Not authorized to view these ratings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        ratings = self.get_queryset().filter(service_request=service_request)
        serializer = self.get_serializer(ratings, many=True)
        return Response(serializer.data)


# Import serializers at the bottom to avoid circular imports
try:
    from rest_framework import serializers
except ImportError:
    serializers = None
