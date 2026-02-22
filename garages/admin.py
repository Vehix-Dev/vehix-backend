from django.contrib import admin
from .models import Garage, GarageServiceRequest


@admin.register(Garage)
class GarageAdmin(admin.ModelAdmin):
    list_display = ['name', 'garage_type', 'verification_status', 'owner_name', 'primary_phone', 'registration_date']
    list_filter = ['verification_status', 'garage_type', 'vehicle_types', 'services_offered']
    search_fields = ['name', 'owner_name', 'primary_phone', 'business_email']
    readonly_fields = ['submission_completeness', 'registration_date', 'registration_ip', 'device_type', 'verified_at']
    fieldsets = (
        ('Garage Identity', {
            'fields': ('name', 'garage_type', 'years_in_operation', 'physical_address', 'latitude', 'longitude', 'operating_hours', 'primary_phone', 'secondary_phone', 'business_email')
        }),
        ('Ownership & Management', {
            'fields': ('owner_name', 'owner_national_id', 'owner_id_front', 'owner_id_back', 'owner_phone', 'owner_email', 'emergency_contact_name', 'emergency_contact_phone', 'manager_name', 'manager_phone', 'manager_email')
        }),
        ('Legal & Business Documents', {
            'fields': ('business_registration_cert', 'tin_tax_id', 'trading_license', 'local_authority_letter')
        }),
        ('Workshop Proof', {
            'fields': ('exterior_photo', 'interior_workshop_photo', 'tools_equipment_photo')
        }),
        ('Services Offered', {
            'fields': ('vehicle_types', 'services_offered', 'services_not_offered')
        }),
        ('Pricing Information', {
            'fields': ('pricing_info', 'is_price_negotiable')
        }),
        ('Staff & Skills', {
            'fields': ('mechanics_count', 'lead_mechanic_name', 'experience_years', 'certifications', 'specialized_skills')
        }),
        ('Service Policies', {
            'fields': ('warranty_offered', 'warranty_duration_days', 'avg_turnaround_hours', 'emergency_service_available', 'working_days', 'cancellation_policy')
        }),
        ('Banking & Payments', {
            'fields': ('payment_method', 'account_holder_name', 'account_number', 'provider_name', 'settlement_preference')
        }),
        ('Compliance & Agreements', {
            'fields': ('terms_accepted', 'terms_accepted_at', 'terms_accepted_ip')
        }),
        ('Verification', {
            'fields': ('verification_status', 'verified_by', 'verified_at', 'rejection_reason', 'suspension_reason')
        }),
        ('System Metadata', {
            'fields': ('submission_completeness', 'registration_date', 'registration_ip', 'device_type'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GarageServiceRequest)
class GarageServiceRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'rider', 'garage', 'service_category', 'status', 'preferred_date', 'created_at']
    list_filter = ['status', 'service_category', 'vehicle_type', 'preferred_date']
    search_fields = ['rider__username', 'garage__name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Request Details', {
            'fields': ('rider', 'garage', 'vehicle_type', 'service_category', 'description')
        }),
        ('Scheduling', {
            'fields': ('preferred_date', 'preferred_time', 'location_lat', 'location_lng')
        }),
        ('Status & Cost', {
            'fields': ('status', 'estimated_cost', 'actual_cost')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
