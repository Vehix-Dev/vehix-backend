from django.contrib import admin
from django.db import transaction
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import ServiceRequest


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
 
    list_display = (
        'id', 'service_type', 'status', 'rider', 'rodie', 
        'is_paid', 'fee_charged', 'accepted_at', 'en_route_at', 
        'started_at', 'completed_at', 'created_at'
    )
    
    list_filter = ('status', 'service_type', 'is_paid', 'fee_charged')
    search_fields = ('rider__username', 'rodie__username', 'rider__email', 'rodie__email')
    
    
    readonly_fields = (
        'created_at', 'updated_at', 'accepted_at', 'en_route_at', 
        'started_at', 'completed_at'
    )
    
    actions = ['charge_selected_fees']
    
    
    fieldsets = (
        ('User Information', {
            'fields': ('rider', 'rodie')
        }),
        ('Service Information', {
            'fields': ('service_type', 'status')
        }),
        ('Location Coordinates', {
            'fields': ('rider_lat', 'rider_lng'),
            'description': 'Geographic coordinates for the rider'
        }),
        ('Payment Status', {
            'fields': ('is_paid', 'fee_charged')
        }),
        ('Timestamps', {
            'fields': (
                ('accepted_at', 'en_route_at'),
                ('started_at', 'completed_at'),
                ('created_at', 'updated_at')
            ),
            'classes': ('collapse',)
        }),
    )
    
   
    date_hierarchy = 'created_at'
    
    def charge_selected_fees(self, request, queryset):
        """Custom admin action to charge fees for selected requests"""
        from .models import charge_fee_for_request 
        
        processed = 0
        failed = 0
        
        for req in queryset:
            try:
                if not req.fee_charged and req.status == 'COMPLETED':
                    success = charge_fee_for_request(req)
                    if success:
                        processed += 1
                    else:
                        failed += 1
                else:
                    self.message_user(
                        request, 
                        f"Request {req.id} skipped: Status={req.status}, Fee already charged={req.fee_charged}",
                        level=messages.WARNING
                    )
            except Exception as e:
                failed += 1
                self.message_user(
                    request, 
                    f"Error charging fee for request {req.id}: {str(e)}",
                    level=messages.ERROR
                )
        
        if processed > 0:
            self.message_user(
                request, 
                f'Successfully charged fees for {processed} request(s).',
                level=messages.SUCCESS
            )
        if failed > 0:
            self.message_user(
                request, 
                f'Failed to charge {failed} request(s). Check logs for details.',
                level=messages.WARNING
            )
    
    charge_selected_fees.short_description = 'Charge fees for selected completed requests'
    
    def get_queryset(self, request):
        """Optimize queryset by selecting related objects"""
        queryset = super().get_queryset(request)
        return queryset.select_related('rider', 'rodie', 'service_type')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize foreign key dropdowns"""
        if db_field.name == "rider":
            from users.models import User
            kwargs["queryset"] = User.objects.filter(role='RIDER')
        elif db_field.name == "rodie":
            from users.models import User
            kwargs["queryset"] = User.objects.filter(role='RODIE')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        """
        Custom save method with proper transaction handling
        """
        try:
            obj.full_clean()
            with transaction.atomic():
                super().save_model(request, obj, form, change)
                
                if change:
                    action = "updated"
                else:
                    action = "created"
                
                self.message_user(
                    request, 
                    f'ServiceRequest #{obj.id} was {action} successfully.',
                    level=messages.SUCCESS
                )
                    
        except ValidationError as e:
            error_message = 'Cannot save ServiceRequest: '
            if hasattr(e, 'message_dict'):
                for field, errors in e.message_dict.items():
                    error_message += f'{field}: {", ".join(errors)} '
            else:
                error_message += str(e)
            
            self.message_user(request, error_message, level=messages.ERROR)
            raise
            
        except Exception as e:
            self.message_user(
                request, 
                f'Error saving ServiceRequest: {str(e)}',
                level=messages.ERROR
            )
            raise
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make certain fields read-only based on object state
        """
        readonly_fields = list(self.readonly_fields)
        
        if obj and obj.pk:  
            readonly_fields.append('rider')
            timestamp_fields = ['accepted_at', 'en_route_at', 'started_at', 'completed_at']
            for field in timestamp_fields:
                if getattr(obj, field):
                    readonly_fields.append(field)
        
        return tuple(readonly_fields)
    
    def get_fieldsets(self, request, obj=None):
        """
        Dynamically adjust fieldsets based on object state
        """
        fieldsets = super().get_fieldsets(request, obj)
        
        if not obj:
            new_fieldsets = []
            for name, data in fieldsets:
                if name == 'Timestamps':
                    data = {
                        'fields': data['fields'],
                        'classes': ('collapse', 'grp-collapse grp-closed'),
                    }
                new_fieldsets.append((name, data))
            return new_fieldsets
        
        return fieldsets