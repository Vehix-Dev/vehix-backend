import os
import uuid
import zipfile
import logging
from datetime import datetime
from io import BytesIO

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend

from .models import UserImage, UserImageStorage
from .serializers import (
    UserImageSerializer,
    ImageUploadSerializer,
    AdminImageSerializer,
    AdminImageUploadSerializer,
    AdminBulkImageUploadSerializer
)

logger = logging.getLogger(__name__)
User = get_user_model()


class UserImageViewSet(viewsets.ModelViewSet):
    """API for users to manage their own images"""
    serializer_class = UserImageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        return UserImage.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        serializer = ImageUploadSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            image_instance = serializer.save()
            full_serializer = UserImageSerializer(
                image_instance,
                context={'request': request}
            )
            return Response(full_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get images by type"""
        image_type = request.query_params.get('type', None)
        if image_type:
            queryset = self.get_queryset().filter(image_type=image_type)
        else:
            queryset = self.get_queryset()
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def thumbnails(self, request):
        """Get only thumbnails for user"""
        queryset = self.get_queryset()
        thumbnails = [
            {
                'id': img.id,
                'image_type': img.image_type,
                'thumbnail_url': request.build_absolute_uri(img.thumbnail.url) if img.thumbnail else None,
                'status': img.status,
                'created_at': img.created_at
            }
            for img in queryset if img.thumbnail
        ]
        return Response(thumbnails)


class AdminImageViewSet(viewsets.ModelViewSet):
    """Admin API for managing all images (with authentication for write operations)"""
    serializer_class = AdminImageSerializer
    queryset = UserImage.objects.all().order_by('-created_at')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['external_id', 'image_type', 'status', 'user__role']
    search_fields = ['external_id', 'user__username', 'user__phone', 'description']
    ordering_fields = ['created_at', 'external_id', 'file_size', 'updated_at']
    
    def get_permissions(self):
        action = getattr(self, 'action', None)
        if action in ['list', 'retrieve']:
            return [AllowAny()]
        else:
            return [IsAdminUser()]
    
    def get_parsers(self):
        action = getattr(self, 'action', None)
        if action == 'create':
            return [MultiPartParser(), FormParser()]
        return [JSONParser(), MultiPartParser(), FormParser()]


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_upload_for_user(request):
    """Admin upload image for specific user"""
    serializer = AdminImageUploadSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        image_instance = serializer.save()
        full_serializer = AdminImageSerializer(
            image_instance,
            context={'request': request}
        )
        return Response(full_serializer.data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_bulk_upload(request):
    """Admin bulk upload multiple images for a user"""
    serializer = AdminBulkImageUploadSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        result = serializer.save()
        return Response({
            'message': f'Successfully uploaded {result["count"]} images',
            'external_id': request.data.get('external_id'),
            'image_type': request.data.get('image_type'),
            'created_ids': [img.id for img in result['images']]
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def all_thumbnails_view(request):
    """Get all thumbnails with basic info (no auth required)"""
    queryset = UserImage.objects.all().order_by('-created_at')
    external_id = request.query_params.get('external_id', None)
    if external_id:
        queryset = queryset.filter(external_id=external_id)
    
    prefix = request.query_params.get('prefix', None)
    if prefix:
        queryset = queryset.filter(external_id__startswith=prefix)
    
    image_type = request.query_params.get('image_type', None)
    if image_type:
        queryset = queryset.filter(image_type=image_type)
    
    status_filter = request.query_params.get('status', None)
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    role = request.query_params.get('role', None)
    if role:
        queryset = queryset.filter(user__role=role)
    
    search = request.query_params.get('search', None)
    if search:
        queryset = queryset.filter(
            Q(external_id__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__phone__icontains=search) |
            Q(description__icontains=search)
        )
    
    thumbnails = []
    for img in queryset:
        if img.thumbnail:
            thumbnails.append({
                'id': img.id,
                'external_id': img.external_id,
                'image_type': img.image_type,
                'thumbnail_url': request.build_absolute_uri(img.thumbnail.url) if img.thumbnail else None,
                'original_url': request.build_absolute_uri(img.original_image.url) if img.original_image else None,
                'user_role': img.user.role,
                'status': img.status,
                'created_at': img.created_at,
                'description': img.description
            })
    
    return Response({
        'count': len(thumbnails),
        'thumbnails': thumbnails
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def images_by_user_view(request):
    """Get all images for a specific user by external_id (no auth required)"""
    external_id = request.query_params.get('external_id', None)
    if not external_id:
        return Response(
            {'error': 'external_id parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    image_type = request.query_params.get('image_type', None)
    status_filter = request.query_params.get('status', None)
    
    queryset = UserImage.objects.filter(external_id=external_id)
    
    if image_type:
        queryset = queryset.filter(image_type=image_type)
    
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    serializer = AdminImageSerializer(queryset, many=True, context={'request': request})
    
    user = User.objects.filter(external_id=external_id).first()
    user_info = None
    if user:
        user_info = {
            'id': user.id,
            'username': user.username,
            'phone': user.phone,
            'role': user.role,
            'email': user.email,
            'is_approved': user.is_approved,
            'created_at': user.created_at
        }
    
    return Response({
        'user': user_info,
        'images': serializer.data,
        'count': queryset.count()
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def update_image_status_view(request, pk):
    """Update image status (approve/reject) - requires admin"""
    try:
        image = UserImage.objects.get(id=pk)
    except UserImage.DoesNotExist:
        return Response(
            {'error': 'Image not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    new_status = request.data.get('status')
    
    if new_status in dict(UserImage.STATUS_CHOICES):
        image.status = new_status
        image.save()
        admin_user = request.user.username if request.user.is_authenticated else 'System'
        
        return Response({
            'status': 'updated',
            'new_status': new_status,
            'image_id': image.id,
            'external_id': image.external_id,
            'updated_by': admin_user,
            'updated_at': image.updated_at
        })
    
    return Response(
        {'error': 'Invalid status'},
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_update_status_view(request):
    """Bulk update status for multiple images"""
    image_ids = request.data.get('image_ids', [])
    new_status = request.data.get('status')
    
    if not image_ids:
        return Response(
            {'error': 'image_ids is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if new_status not in dict(UserImage.STATUS_CHOICES):
        return Response(
            {'error': 'Invalid status'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    updated_count = UserImage.objects.filter(id__in=image_ids).update(status=new_status)
    
    return Response({
        'message': f'Updated {updated_count} images',
        'status': new_status,
        'updated_count': updated_count
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def download_user_images_view(request):
    """Download all images for a user as a zip file"""
    external_id = request.query_params.get('external_id', None)
    if not external_id:
        return Response(
            {'error': 'external_id parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    images = UserImage.objects.filter(external_id=external_id)
    
    if not images.exists():
        return Response(
            {'error': f'No images found for user {external_id}'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for image in images:
            if image.original_image and os.path.exists(image.original_image.path):
                arcname = f"{external_id}/{image.image_type}/original_{image.id}_{os.path.basename(image.original_image.name)}"
                zip_file.write(image.original_image.path, arcname)
            
            if image.thumbnail and os.path.exists(image.thumbnail.path):
                arcname = f"{external_id}/{image.image_type}/thumbnail_{image.id}_{os.path.basename(image.thumbnail.name)}"
                zip_file.write(image.thumbnail.path, arcname)
    
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{external_id}_images_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip"'
    
    return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_replace_image(request, image_id):
    """Admin API to replace an existing image"""
    try:
        image = UserImage.objects.get(id=image_id)
    except UserImage.DoesNotExist:
        return Response(
            {'error': 'Image not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if 'image' not in request.FILES:
        return Response(
            {'error': 'No image file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if image.original_image and os.path.exists(image.original_image.path):
        os.remove(image.original_image.path)
    
    if image.thumbnail and os.path.exists(image.thumbnail.path):
        os.remove(image.thumbnail.path)
    
    new_image = request.FILES['image']
    image.original_image = new_image
    image.original_filename = new_image.name
    image.status = 'PENDING'  
    image.save()
    
    serializer = AdminImageSerializer(image, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def user_images_by_type_view(request):
    """Get all images for a user by type"""
    external_id = request.query_params.get('external_id', None)
    image_type = request.query_params.get('type', None)
    
    if not external_id:
        return Response(
            {'error': 'external_id parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    queryset = UserImage.objects.filter(external_id=external_id)
    
    if image_type:
        queryset = queryset.filter(image_type=image_type)
    
    serializer = AdminImageSerializer(queryset, many=True, context={'request': request})
    
    return Response({
        'external_id': external_id,
        'image_type': image_type,
        'images': serializer.data,
        'count': queryset.count()
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def user_thumbnails_view(request):
    """Get thumbnails for a specific user"""
    external_id = request.query_params.get('external_id', None)
    
    if not external_id:
        return Response(
            {'error': 'external_id parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    images = UserImage.objects.filter(external_id=external_id)
    
    thumbnails = []
    for img in images:
        if img.thumbnail:
            thumbnails.append({
                'id': img.id,
                'image_type': img.image_type,
                'thumbnail_url': request.build_absolute_uri(img.thumbnail.url) if img.thumbnail else None,
                'status': img.status,
                'created_at': img.created_at
            })
    
    return Response({
        'external_id': external_id,
        'thumbnails': thumbnails,
        'count': len(thumbnails)
    })


@api_view(['GET'])
def file_structure_view(request):
    """Get the complete file structure for all user images"""
    base_path = os.path.join(settings.MEDIA_ROOT, 'user_images')
    structure = {}
    
    def scan_directory(path, relative_path=''):
        if not os.path.exists(path):
            return {}
        
        items = {}
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            rel_item_path = os.path.join(relative_path, item) if relative_path else item
            
            if os.path.isdir(item_path):
                items[item] = {
                    'type': 'directory',
                    'path': rel_item_path,
                    'contents': scan_directory(item_path, rel_item_path)
                }
            else:
                items[item] = {
                    'type': 'file',
                    'path': rel_item_path,
                    'size': os.path.getsize(item_path),
                    'modified': os.path.getmtime(item_path)
                }
        
        return items
    
    structure = scan_directory(base_path)
    
    total_files = 0
    total_size = 0
    
    def count_stats(items):
        nonlocal total_files, total_size
        for key, value in items.items():
            if value['type'] == 'file':
                total_files += 1
                total_size += value.get('size', 0)
            elif value['type'] == 'directory':
                count_stats(value.get('contents', {}))
    
    count_stats(structure)
    
    return Response({
        'structure': structure,
        'statistics': {
            'total_files': total_files,
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'base_path': base_path
        }
    })