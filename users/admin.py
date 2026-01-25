from django.contrib import admin
from .models import User, Wallet, WalletTransaction
from .models import Referral
from .models import Notification
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import STKPushDepositForm
from .models import Payment
from .pesapal import PesapalClient
import uuid
from services.models import RodieService



class RodieServiceInline(admin.TabularInline):
    model = RodieService
    extra = 0
    verbose_name = 'Service Provided'
    verbose_name_plural = 'Services Provided'


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('external_id', 'username', 'email', 'role', 'wallet_balance', 'stk_deposit_link', 'is_active', 'is_approved')
    list_filter = ('role', 'is_active', 'is_approved')
    search_fields = ('external_id', 'username', 'email', 'phone')
    readonly_fields = ('external_id', 'referral_code')
    fieldsets = (
        (None, {'fields': ('external_id', 'username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        ('Identifiers', {'fields': ('role', 'referral_code')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_approved')}),
    )

    inlines = [RodieServiceInline]

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
        if getattr(obj, 'role', None) != 'RODIE':
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
        ]
        return custom_urls + urls

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
    list_display = ('user', 'title', 'read', 'created_at')
    search_fields = ('user__username', 'title', 'body')
