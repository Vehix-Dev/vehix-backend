from django.contrib import admin
from .models import User, Wallet, WalletTransaction, PlatformConfig
from .models import Referral
from .models import Notification
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from .forms import STKPushDepositForm
from .models import Payment
from .pesapal import PesapalClient
import uuid
from services.models import RodieService
from django.db.models import Q



class RodieServiceInline(admin.TabularInline):
    model = RodieService
    extra = 0
    verbose_name = 'Service Provided'
    verbose_name_plural = 'Services Provided'


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'external_id',
        'username',
        'email',
        'role',
        'wallet_balance',
        'is_deleted',
        'deletion_status',
        'deletion_requested_at',
        'stk_deposit_link',
        'is_active',
        'is_approved',
    )
    list_filter = ('role', 'is_active', 'is_approved', 'is_deleted', 'deletion_status')
    search_fields = ('external_id', 'username', 'email', 'phone')
    readonly_fields = ('external_id', 'referral_code', 'deletion_requested_at')
    actions = ['restore_users', 'mark_as_deleted', 'mark_pending_deletion', 'permanently_delete_users']
    fieldsets = (
        (None, {'fields': ('external_id', 'username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        ('Identifiers', {'fields': ('role', 'referral_code')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_approved')}),
        ('Deletion', {'fields': ('is_deleted', 'deletion_status', 'deletion_requested_at', 'deletion_reason')}),
    )

    inlines = [RodieServiceInline]

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['mechanics_url'] = '/admin/users/user/mechanics/'
        if request.GET.get('role') == 'MECHANIC':
            extra_context['mechanics_link'] = format_html('<a href="/admin/users/user/mechanics/">View All Mechanics</a>')
        return super().changelist_view(request, extra_context)

    def save_model(self, request, obj, form, change):
        if getattr(obj, 'is_superuser', False) or getattr(obj, 'is_staff', False):
            obj.role = 'ADMIN'
            obj.is_staff = True
            obj.is_superuser = True
            obj.is_approved = True
            obj.is_active = True

        if getattr(obj, 'role', None) == 'ADMIN':
            obj.is_staff = True
            obj.is_superuser = True
            obj.is_approved = True
            obj.is_active = True

        if getattr(obj, 'username', None):
            obj.username = obj.username.strip()

        
        try:
            changed = getattr(form, 'changed_data', [])
        except Exception:
            changed = []

        if 'password' in changed:
            pw = form.cleaned_data.get('password') if hasattr(form, 'cleaned_data') else getattr(obj, 'password', None)
            if pw and ('$' not in pw):
                obj.set_password(pw)

        super().save_model(request, obj, form, change)

    def wallet_balance(self, obj):
        try:
            return obj.wallet.balance
        except Exception:
            return 0
    wallet_balance.short_description = 'Wallet Balance'
    
    def services_list(self, obj):
        if getattr(obj, 'role', None) not in ('RODIE', 'MECHANIC'):
            return ''
        qs = RodieService.objects.filter(rodie=obj).select_related('service')
        items = ', '.join([s.service.name for s in qs])
        return format_html(items)
    services_list.short_description = 'Services'

    def stk_deposit_link(self, obj):
        return format_html('<a class="button" href="{}/stk-deposit/">Deposit</a>', obj.pk)
    stk_deposit_link.short_description = 'STK Push'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:user_id>/stk-deposit/', self.admin_site.admin_view(self.stk_deposit_view), name='user-stk-deposit'),
            path('deleted/', self.admin_site.admin_view(self.deleted_users_view), name='users_user_deleted'),
            path('deleted/riders/', self.admin_site.admin_view(self.deleted_riders_view), name='users_user_deleted_riders'),
            path('deleted/roadies/', self.admin_site.admin_view(self.deleted_roadies_view), name='users_user_deleted_roadies'),
            path('pending-deletions/', self.admin_site.admin_view(self.pending_deletions_view), name='users_user_pending_deletions'),
            path('<int:user_id>/restore/', self.admin_site.admin_view(self.restore_user_view), name='users_user_restore'),
            path('<int:user_id>/permanent-delete/', self.admin_site.admin_view(self.permanent_delete_user_view), name='users_user_permanent_delete'),
            path('mechanics/', self.admin_site.admin_view(self.mechanics_view), name='users_user_mechanics'),
        ]
        return custom_urls + urls

    def deleted_users_view(self, request):
        users = User.objects.filter(is_deleted=True).order_by('-updated_at')
        context = {
            **self.admin_site.each_context(request),
            'title': 'Deleted Users',
            'users': users,
            'opts': self.model._meta,
        }
        return render(request, 'admin/users/deleted_users.html', context)

    def deleted_riders_view(self, request):
        users = User.objects.filter(role='RIDER', is_deleted=True).order_by('-updated_at')
        context = {
            **self.admin_site.each_context(request),
            'title': 'Deleted Riders',
            'users': users,
            'opts': self.model._meta,
        }
        return render(request, 'admin/users/deleted_users.html', context)

    def deleted_roadies_view(self, request):
        users = User.objects.filter(role='RODIE', is_deleted=True).order_by('-updated_at')
        context = {
            **self.admin_site.each_context(request),
            'title': 'Deleted Roadies',
            'users': users,
            'opts': self.model._meta,
        }
        return render(request, 'admin/users/deleted_users.html', context)

    def pending_deletions_view(self, request):
        users = User.objects.filter(deletion_status='PENDING').order_by('-deletion_requested_at')
        context = {
            **self.admin_site.each_context(request),
            'title': 'Pending Deletion Requests',
            'users': users,
            'opts': self.model._meta,
        }
        return render(request, 'admin/users/pending_deletions.html', context)

    def restore_user_view(self, request, user_id):
        user = self.get_object(request, user_id)
        if user:
            user.is_deleted = False
            user.is_active = True
            user.deletion_status = None
            user.deletion_requested_at = None
            user.save()
            self.message_user(request, f'User {user.username} restored successfully.', messages.SUCCESS)
        return redirect('admin:users_user_deleted')

    def permanent_delete_user_view(self, request, user_id):
        user = self.get_object(request, user_id)
        if user:
            username = user.username
            user.delete()
            self.message_user(request, f'User {username} permanently deleted.', messages.SUCCESS)
        return redirect('admin:users_user_deleted')

    def restore_users(self, request, queryset):
        updated = queryset.filter(is_deleted=True).update(is_deleted=False, is_active=True, deletion_status=None, deletion_requested_at=None)
        self.message_user(request, f'{updated} user(s) restored successfully.')
    restore_users.short_description = 'Restore selected deleted users'

    def mark_as_deleted(self, request, queryset):
        updated = queryset.update(is_deleted=True, is_active=False)
        self.message_user(request, f'{updated} user(s) marked as deleted.')
    mark_as_deleted.short_description = 'Mark selected users as deleted'

    def mark_pending_deletion(self, request, queryset):
        updated = queryset.update(deletion_status='PENDING', deletion_requested_at=timezone.now())
        self.message_user(request, f'{updated} user(s) marked as pending deletion.')
    mark_pending_deletion.short_description = 'Mark selected users as pending deletion'

    def permanently_delete_users(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'{count} user(s) permanently deleted.')
    permanently_delete_users.short_description = 'Permanently delete selected users'

    def stk_deposit_view(self, request, user_id):
        user = self.get_object(request, user_id)
        if not user:
            return redirect('admin:users_user_changelist')

        if request.method == 'POST':
            form = STKPushDepositForm(request.POST)
            if form.is_valid():
                phone_number = form.cleaned_data['phone_number']
                amount = form.cleaned_data['amount']
                description = form.cleaned_data['description'] or f"Admin Deposit for {user.username}"

                reference = f"ADM-{uuid.uuid4().hex[:12].upper()}"
                payment = Payment.objects.create(
                    user=user,
                    amount=amount,
                    transaction_type='DEPOSIT',
                    status='PENDING',
                    reference=reference,
                    description=description
                )

                try:
                    client = PesapalClient()
                    callback_url = request.build_absolute_uri('/api/payments/pesapal/ipn/') 
                    order_res = client.submit_order(payment, callback_url)
                    tracking_id = order_res.get('order_tracking_id')
                    payment.processor_id = tracking_id
                    payment.save()

                    stk_res = client.submit_mobile_payment(tracking_id, phone_number)
                    if stk_res.get('status') == '200':
                        self.message_user(request, f"STK Push sent to {phone_number} for {amount} KES.", messages.SUCCESS)
                    else:
                        self.message_user(request, f"PesaPal API Error: {stk_res.get('message', 'Unknown error')}", messages.ERROR)
                except Exception as e:
                    self.message_user(request, f"Error: {str(e)}", messages.ERROR)

                return redirect('admin:users_user_changelist')
        else:
            form = STKPushDepositForm(initial={'phone_number': user.phone})

        context = {
            **self.admin_site.each_context(request),
            'title': f'Trigger STK Push for {user.username}',
            'form': form,
            'user_obj': user,
            'opts': self.model._meta,
        }
        return render(request, 'admin/users/stk_deposit.html', context)

    def mechanics_view(self, request):
        mechanics = User.objects.filter(role='MECHANIC').select_related('wallet')
        context = {
            **self.admin_site.each_context(request),
            'title': 'Mechanics (Former Roadies)',
            'mechanics': mechanics,
            'opts': self.model._meta,
        }
        return render(request, 'admin/users/mechanics.html', context)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance')
    search_fields = ('user__username', 'user__email', 'user__phone')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'amount', 'reason', 'created_at')
    search_fields = ('wallet__user__username', 'reason')


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referrer', 'referred', 'amount', 'created_at')
    search_fields = ('referrer__username', 'referred__username')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'target_role', 'title', 'notification_type', 'is_read', 'url', 'created_at')
    list_filter = ('target_role', 'notification_type', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'title', 'message', 'url')


@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    list_display = ('max_negative_balance', 'trial_days', 'updated_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'user', 'amount', 'transaction_type', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('reference', 'user__username', 'processor_id')

