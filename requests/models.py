from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

User = get_user_model()


class CancellationReason(models.Model):
    """Predefined cancellation reasons for different user roles"""
    
    ROLE_CHOICES = (
        ('RIDER', 'Rider'),
        ('RODIE', 'Roadie'),
    )
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    reason = models.CharField(max_length=100)
    requires_custom_text = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['role', 'order', 'reason']
        unique_together = ['role', 'reason']
    
    def __str__(self):
        return f"{self.role}: {self.reason}"


class RequestCancellation(models.Model):
    """Track cancellation details for service requests"""
    
    request = models.OneToOneField(
        'ServiceRequest',
        on_delete=models.CASCADE,
        related_name='cancellation'
    )
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='cancellations_made'
    )
    reason = models.ForeignKey(
        CancellationReason,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cancellations'
    )
    custom_reason_text = models.TextField(blank=True, null=True)
    cancelled_at = models.DateTimeField(auto_now_add=True)
    
    # Additional context
    distance_at_cancellation = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Distance between rider and roadie at time of cancellation (in km)"
    )
    time_to_arrival_at_cancellation = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Estimated time to arrival at cancellation (in seconds)"
    )
    
    class Meta:
        ordering = ['-cancelled_at']
    
    def __str__(self):
        return f"Request #{self.request.id} cancelled by {self.cancelled_by.get_role_display()}"
    
    @property
    def display_reason(self):
        """Get the full reason for display"""
        if self.reason:
            if self.reason.requires_custom_text and self.custom_reason_text:
                return f"{self.reason.reason}: {self.custom_reason_text}"
            return self.reason.reason
        return self.custom_reason_text or "No reason provided"


class ServiceRequest(models.Model):

    STATUS_CHOICES = (
        ('REQUESTED', 'Requested'),
        ('ACCEPTED', 'Accepted'),
        ('EN_ROUTE', 'En Route'),
        ('ARRIVED', 'Arrived'),
        ('STARTED', 'Service Started'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    )

    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rider_requests',
        limit_choices_to={'role': 'RIDER'}
    )

    rodie = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rodie_requests',
        limit_choices_to={'role': 'RODIE'}
    )

    service_type = models.ForeignKey(
        'services.ServiceType',
        on_delete=models.PROTECT
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='REQUESTED'
    )

    rider_lat = models.DecimalField(max_digits=9, decimal_places=6)
    rider_lng = models.DecimalField(max_digits=9, decimal_places=6)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    fee_charged = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    en_route_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Request #{self.id} - {self.service_type} - {self.status}"

    def clean(self):
        """Validate that rider and rodie wallets are above the allowed negative balance.
        This prevents creating or assigning requests to users who are below the platform's allowed negative balance.
        """
        try:
            from users.models import Wallet, PlatformConfig
            cfg = PlatformConfig.objects.first()
            max_neg = cfg.max_negative_balance if cfg else Decimal('0')
            if self.rider:
                rider_wallet, _ = Wallet.objects.get_or_create(user=self.rider)
                if rider_wallet.balance < Decimal(-max_neg):
                    raise ValidationError({'rider': 'Rider wallet below allowed negative balance; cannot create request.'})
            if self.rodie:
                rodie_wallet, _ = Wallet.objects.get_or_create(user=self.rodie)
                if rodie_wallet.balance < Decimal(-max_neg):
                    raise ValidationError({'rodie': 'Rodie wallet below allowed negative balance; cannot assign request.'})
        except ValidationError:
            raise
        except Exception:
            return


from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal


def process_referral_reward(user_id):
    """Check if the user was referred and award the referrer if this is their first completion."""
    try:
        from users.models import Referral, Wallet, WalletTransaction, User
        user = User.objects.get(id=user_id)
        
        # Check if user was referred and reward not yet paid
        referral = Referral.objects.filter(referred=user, is_credited=False).first()
        if not referral:
            return

        # Count total completions for this user (including the one just finished)
        completions = ServiceRequest.objects.filter(
            models.Q(rider=user) | models.Q(rodie=user),
            status='COMPLETED'
        ).count()

        if completions == 1:
            with transaction.atomic():
                # Re-fetch with lock
                ref = Referral.objects.select_for_update().get(id=referral.id)
                if ref.is_credited:
                    return

                # Award the referrer
                ref_wallet, _ = Wallet.objects.get_or_create(user=ref.referrer)
                ref_wallet.balance += ref.amount
                ref_wallet.save(update_fields=['balance'])
                
                WalletTransaction.objects.create(
                    wallet=ref_wallet,
                    amount=ref.amount,
                    reason=f"Referral reward: {user.username} first assist"
                )
                
                ref.is_credited = True
                ref.save(update_fields=['is_credited'])
                print(f"🎁 UGX {ref.amount} referral reward paid to {ref.referrer.username} for {user.username}")
    except Exception as e:
        print(f"❌ Error processing referral reward: {e}")


def charge_fee_for_request(request_id):
    """Charge platform service fee and process referral rewards."""
    try:
        instance = ServiceRequest.objects.get(id=request_id)
        
        # 1. Process Referral Rewards (for both Rider and Roadie)
        process_referral_reward(instance.rider_id)
        if instance.rodie_id:
            process_referral_reward(instance.rodie_id)
            
        # 2. Charge Fee to Roadie
        if not instance.rodie or instance.fee_charged:
            return True
        from users.models import Wallet, PlatformConfig, WalletTransaction
        cfg_data = cache.get("platform_config")
        if not cfg_data:
            cfg = PlatformConfig.objects.first()
            if cfg:
                cfg_data = {'service_fee': cfg.service_fee, 'trial_days': cfg.trial_days}
                cache.set("platform_config", cfg_data, timeout=3600)
        
        fee = cfg_data['service_fee'] if cfg_data else Decimal('0')

        # Trial check — use the trial_end_date set on approval (resets on re-approval)
        if instance.rodie.trial_end_date and timezone.now() < instance.rodie.trial_end_date:
            ServiceRequest.objects.filter(id=instance.id).update(fee_charged=True)
            return True

        # Check if already charged in this or another transaction
        existing = WalletTransaction.objects.filter(
            reason=f'service fee for request {instance.id}', 
            wallet__user=instance.rodie
        ).exists()
        
        if existing:
            ServiceRequest.objects.filter(id=instance.id).update(fee_charged=True)
            return True

        # Perform charging
        with transaction.atomic():
            wallet, _ = Wallet.objects.get_or_create(user=instance.rodie)
            wallet.balance -= Decimal(fee)
            wallet.save(update_fields=['balance'])
            
            WalletTransaction.objects.create(
                wallet=wallet, 
                amount=Decimal(-fee), 
                reason=f'service fee for request {instance.id}'
            )
            
            # Update request status directly to avoid re-triggering signals
            ServiceRequest.objects.filter(id=instance.id).update(fee_charged=True)
            
        return True
    except Exception as e:
        print(f"❌ Error charging fee: {e}")
        return False


@receiver(post_save, sender=ServiceRequest)
def charge_service_fee(sender, instance, created, **kwargs):
    if instance.status == 'COMPLETED' and not instance.fee_charged:
        try:
            from .tasks import process_completion_task
            process_completion_task.delay(instance.id)
        except Exception as e:
            # Fallback to thread if celery is not available
            import threading
            threading.Thread(target=charge_fee_for_request, args=(instance.id,), daemon=True).start()
