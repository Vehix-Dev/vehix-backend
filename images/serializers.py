from rest_framework import serializers
from .models import UserImage
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

User = get_user_model()


class UserImageSerializer(serializers.ModelSerializer):
    original_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    user_details = serializers.SerializerMethodField()
    
    class Meta:
        model = UserImage
        fields = [
            'id', 'user', 'external_id', 'image_type',
            'original_image', 'thumbnail', 'status',
            'description', 'created_at', 'updated_at',
            'file_size', 'width', 'height',
            'original_url', 'thumbnail_url', 'user_details'
        ]
        read_only_fields = [
            'original_image', 'thumbnail', 'created_at',
            'updated_at', 'file_size', 'width', 'height',
            'original_url', 'thumbnail_url'
        ]
    
    def get_original_url(self, obj):
        request = self.context.get('request')
        if obj.original_image and request:
            return request.build_absolute_uri(obj.original_image.url)
        return None
    
    def get_thumbnail_url(self, obj):
        request = self.context.get('request')
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None
    
    def get_user_details(self, obj):
        return {
            'username': obj.user.username,
            'phone': obj.user.phone,
            'role': obj.user.role,
            'email': obj.user.email
        }
    
    def validate(self, data):
        user = data.get('user') or self.instance.user if self.instance else None
        external_id = data.get('external_id', '')
        
        if user and user.external_id != external_id:
            data['external_id'] = user.external_id
        
        return data


class ImageUploadSerializer(serializers.Serializer):
    """Serializer for regular users to upload their own images"""
    image = serializers.ImageField()
    image_type = serializers.ChoiceField(choices=UserImage.IMAGE_TYPE_CHOICES)
    description = serializers.CharField(required=False, allow_blank=True)
    
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        
        image_instance = UserImage.objects.create(
            user=user,
            external_id=user.external_id or '',
            image_type=validated_data['image_type'],
            original_image=validated_data['image'],
            description=validated_data.get('description', ''),
            original_filename=validated_data['image'].name
        )
        
        return image_instance


class AdminImageUploadSerializer(serializers.Serializer):
    """Serializer for admins to upload images for any user"""
    image = serializers.ImageField()
    image_type = serializers.ChoiceField(choices=UserImage.IMAGE_TYPE_CHOICES)
    external_id = serializers.CharField(max_length=10, required=True)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    auto_approve = serializers.BooleanField(default=False, required=False)
    
    def validate_external_id(self, value):
        """Validate that external_id exists and get the user"""
        try:
            user = User.objects.get(external_id=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError(f"User with external_id '{value}' does not exist")
    
    def validate(self, data):
        """Additional validation"""
        external_id = data.get('external_id')
        
        user = User.objects.filter(external_id=external_id).first()
        if not user:
            raise serializers.ValidationError(f"User with external_id '{external_id}' not found")
        
        data['user'] = user
        return data
    
    def create(self, validated_data):
        """Create image instance for the specified user"""
        user = validated_data['user']
        auto_approve = validated_data.get('auto_approve', False)
        status = 'APPROVED' if auto_approve else 'PENDING'
        
        image_instance = UserImage.objects.create(
            user=user,
            external_id=user.external_id,
            image_type=validated_data['image_type'],
            original_image=validated_data['image'],
            description=validated_data.get('description', ''),
            original_filename=validated_data['image'].name,
            status=status
        )
        
        return image_instance


class AdminBulkImageUploadSerializer(serializers.Serializer):
    """Serializer for bulk image uploads by admin"""
    images = serializers.ListField(
        child=serializers.FileField(),
        required=True
    )
    external_id = serializers.CharField(max_length=10, required=True)
    image_type = serializers.ChoiceField(choices=UserImage.IMAGE_TYPE_CHOICES, required=True)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    auto_approve = serializers.BooleanField(default=False, required=False)
    
    def validate_external_id(self, value):
        """Validate that external_id exists"""
        if not User.objects.filter(external_id=value).exists():
            raise serializers.ValidationError(f"User with external_id '{value}' does not exist")
        return value
    
    def create(self, validated_data):
        """Create multiple image instances"""
        user = User.objects.get(external_id=validated_data['external_id'])
        images = validated_data['images']
        image_type = validated_data['image_type']
        description = validated_data.get('description', '')
        auto_approve = validated_data.get('auto_approve', False)
        status = 'APPROVED' if auto_approve else 'PENDING'
        
        created_images = []
        for image_file in images:
            image_instance = UserImage.objects.create(
                user=user,
                external_id=user.external_id,
                image_type=image_type,
                original_image=image_file,
                description=description,
                original_filename=image_file.name,
                status=status
            )
            created_images.append(image_instance)
        
        return {'images': created_images, 'count': len(created_images)}


class AdminImageSerializer(serializers.ModelSerializer):
    original_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    user_info = serializers.SerializerMethodField()
    
    class Meta:
        model = UserImage
        fields = [
            'id', 'external_id', 'image_type', 'status',
            'original_url', 'thumbnail_url', 'user_info',
            'created_at', 'description', 'file_size',
            'width', 'height', 'mime_type'
        ]
    
    def get_original_url(self, obj):
        request = self.context.get('request')
        if obj.original_image and request:
            return request.build_absolute_uri(obj.original_image.url)
        return None
    
    def get_thumbnail_url(self, obj):
        request = self.context.get('request')
        if obj.thumbnail and request:
            return request.build_absolute_uri(obj.thumbnail.url)
        return None
    
    def get_user_info(self, obj):
        return {
            'username': obj.user.username,
            'phone': obj.user.phone,
            'role': obj.user.role,
            'email': obj.user.email,
            'is_approved': obj.user.is_approved,
            'created_at': obj.user.created_at
        }