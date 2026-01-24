from django.contrib import admin
from .models import UserImage
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(UserImage)
class UserImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'external_id', 'get_user', 'image_type', 'status', 'get_thumbnail', 'created_at']
    list_display_links = ['id', 'external_id']
    list_filter = ['status', 'image_type', 'user__role', 'created_at']
    search_fields = ['external_id', 'user__username', 'user__phone', 'user__email', 'description']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 
        'file_size', 'width', 'height', 'mime_type',
        'original_filename', 'storage_path',
        'get_original_preview', 'get_thumbnail_preview',
        'original_url', 'thumbnail_url'
    ]
    actions = ['approve_selected', 'reject_selected', 'mark_as_pending']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'external_id', 'image_type', 'status', 'description')
        }),
        ('Image Files', {
            'fields': ('original_image', 'thumbnail')
        }),
        ('Image Previews', {
            'fields': ('get_original_preview', 'get_thumbnail_preview'),
            'classes': ('collapse', 'wide')
        }),
        ('URLs', {
            'fields': ('original_url', 'thumbnail_url'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('original_filename', 'storage_path', 'file_size', 
                      'width', 'height', 'mime_type', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_user(self, obj):
        return f"{obj.user.username} ({obj.user.phone})"
    get_user.short_description = 'User'
    get_user.admin_order_field = 'user__username'
    
    def get_thumbnail(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px;" />',
                obj.thumbnail.url
            )
        return "—"
    get_thumbnail.short_description = 'Thumbnail'
    
    def get_original_preview(self, obj):
        if obj.original_image:
            return format_html(
                '<div style="margin: 10px 0;">'
                '<img src="{}" style="max-width: 300px; max-height: 300px; '
                'object-fit: contain; border: 1px solid #ddd; border-radius: 4px;" />'
                '</div>',
                obj.original_image.url
            )
        return "No original image"
    get_original_preview.short_description = 'Original Image Preview'
    
    def get_thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html(
                '<div style="margin: 10px 0;">'
                '<img src="{}" style="max-width: 150px; max-height: 150px; '
                'object-fit: contain; border: 1px solid #ddd; border-radius: 4px;" />'
                '</div>',
                obj.thumbnail.url
            )
        return "No thumbnail"
    get_thumbnail_preview.short_description = 'Thumbnail Preview'
    
    def original_url(self, obj):
        if obj.original_image:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.original_image.url,
                "View Original"
            )
        return "—"
    original_url.short_description = 'Original URL'
    
    def thumbnail_url(self, obj):
        if obj.thumbnail:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.thumbnail.url,
                "View Thumbnail"
            )
        return "—"
    thumbnail_url.short_description = 'Thumbnail URL'
    
    #def get_readonly_fields(self, request, obj=None):
        # When editing an existing object, make image fields read-only
        #if obj:
        #    return self.readonly_fields + ('original_image', 'thumbnail')
       # return self.readonly_fields
    
    def get_fieldsets(self, request, obj=None):
        # When adding a new object, show different fieldset
        if not obj:
            return (
                ('Basic Information', {
                    'fields': ('user', 'external_id', 'image_type', 'status', 'description')
                }),
                ('Image Upload', {
                    'fields': ('original_image',),
                    'description': 'Upload the original image. Thumbnail will be automatically generated.'
                }),
            )
        return super().get_fieldsets(request, obj)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(external_id__isnull=False).order_by('external_id')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def approve_selected(self, request, queryset):
        updated = queryset.update(status='APPROVED')
        self.message_user(request, f'Successfully approved {updated} image(s).')
    approve_selected.short_description = "Approve selected images"
    
    def reject_selected(self, request, queryset):
        updated = queryset.update(status='REJECTED')
        self.message_user(request, f'Successfully rejected {updated} image(s).')
    reject_selected.short_description = "Reject selected images"
    
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='PENDING')
        self.message_user(request, f'Successfully marked {updated} image(s) as pending.')
    mark_as_pending.short_description = "Mark as pending"
    
    def save_model(self, request, obj, form, change):
        if obj.user and not obj.external_id:
            obj.external_id = obj.user.external_id
        
        if 'original_image' in form.changed_data:
            obj.thumbnail = None
        
        super().save_model(request, obj, form, change)
    
    def delete_model(self, request, obj):
        obj.delete()
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    class Media:
        css = {
            'all': (
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
            )
        }
        js = (
            'https://code.jquery.com/jquery-3.6.0.min.js',
        )