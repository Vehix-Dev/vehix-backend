from django.contrib import admin
from .models import ServiceType, RodieService, ServiceSubCategory


class ServiceSubCategoryInline(admin.TabularInline):
    model = ServiceSubCategory
    extra = 0
    fields = ('name', 'description', 'is_active', 'order')


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
	inlines = [ServiceSubCategoryInline]
	list_display = ('name', 'code', 'category', 'is_active', 'has_subcategories', 'rodie_count')
	search_fields = ('name', 'code')

	def rodie_count(self, obj):
		try:
			return RodieService.objects.filter(service=obj).count()
		except Exception:
			return 0
	rodie_count.short_description = 'Roadies Offering'


@admin.register(RodieService)
class RodieServiceAdmin(admin.ModelAdmin):
	list_display = ('rodie', 'service', 'created_at')
	search_fields = ('rodie__username', 'service__name')
