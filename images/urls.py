from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserImageViewSet, 
    AdminImageViewSet, 
    admin_upload_for_user,
    admin_bulk_upload,
    all_thumbnails_view,
    images_by_user_view,
    user_images_by_type_view,
    user_thumbnails_view,
    update_image_status_view,
    bulk_update_status_view,
    download_user_images_view,
    admin_replace_image,
    file_structure_view
)

router = DefaultRouter()
router.register(r'user-images', UserImageViewSet, basename='user-image')
router.register(r'admin-images', AdminImageViewSet, basename='admin-image')

urlpatterns = [
    path('', include(router.urls)),
    path('file-structure/', file_structure_view, name='file-structure'),
    path('admin-upload/', admin_upload_for_user, name='admin-upload'),
    path('bulk-upload/', admin_bulk_upload, name='bulk-upload'),
    path('admin-images/<int:image_id>/replace/', admin_replace_image, name='replace-image'),
    path('thumbnails/', all_thumbnails_view, name='all-thumbnails'),
    path('user-images-by-id/', images_by_user_view, name='user-images-by-id'),
    path('user-images-by-type/', user_images_by_type_view, name='user-images-by-type'),
    path('user-thumbnails/', user_thumbnails_view, name='user-thumbnails'),
    path('admin-images/<int:pk>/update-status/', update_image_status_view, name='update-image-status'),
    path('admin-images/bulk-update-status/', bulk_update_status_view, name='bulk-update-status'),
    path('download-images/', download_user_images_view, name='download-images'),
]