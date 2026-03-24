from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

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


# Signal to charge rodie wallet when a request becomes COMPLETED
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal

@receiver(post_save, sender=ServiceRequest)
def charge_service_fee_initial(sender, instance, created, **kwargs):
    return


def charge_fee_for_request(instance):
    """Charge platform service fee to the rodie's wallet for the given ServiceRequest instance.
    Returns True if charging succeeded and fee_charged was set, False otherwise.
    """
    try:
        from users.models import Wallet, PlatformConfig, WalletTransaction
        cfg = PlatformConfig.objects.first()
        fee = cfg.service_fee if cfg else Decimal('0')
        trial_days = cfg.trial_days if cfg else 0

        if instance.rodie:
            user_age_days = (timezone.now() - instance.rodie.created_at).days
            if user_age_days < trial_days:
                instance.fee_charged = True
                instance.save(update_fields=['fee_charged'])
                return True

            existing = WalletTransaction.objects.filter(reason=f'service fee for request {instance.id}', wallet__user=instance.rodie)
            if existing.exists():
                instance.fee_charged = True
                instance.save(update_fields=['fee_charged'])
                return True
            wallet, _ = Wallet.objects.get_or_create(user=instance.rodie)
            wallet.balance = wallet.balance - Decimal(fee)
            wallet.save()
            WalletTransaction.objects.create(wallet=wallet, amount=Decimal(-fee), reason=f'service fee for request {instance.id}')
        instance.fee_charged = True
        instance.save(update_fields=['fee_charged'])
        return True
    except Exception:
        return False


@receiver(post_save, sender=ServiceRequest)
def charge_service_fee(sender, instance, created, **kwargs):
    if instance.status == 'COMPLETED':
        try:
            from users.models import WalletTransaction
            tx_exists = False
            if instance.rodie:
                tx_exists = WalletTransaction.objects.filter(reason=f'service fee for request {instance.id}', wallet__user=instance.rodie).exists()
            if tx_exists:
                if not instance.fee_charged:
                    instance.fee_charged = True
                    instance.save(update_fields=['fee_charged'])
            else:
                charge_fee_for_request(instance)
        except Exception:
            pass
