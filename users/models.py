from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db import transaction
from django.core.validators import RegexValidator
from django.utils import timezone
import re
import uuid


class User(AbstractUser):
    ROLE_CHOICES = (
        ('RIDER', 'Rider'),
        ('RODIE', 'Rodie'),
        ('MECHANIC', 'Mechanic'),
        ('ADMIN', 'Admin'),
    )

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES
    )

    phone = models.CharField(
        max_length=20,
        unique=True
    )

    referral_code = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        null=True
    )

    nin = models.CharField(
        max_length=14,
        unique=True,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^[A-Za-z0-9]{14}$', message='NIN must be exactly 14 alphanumeric characters')],
        help_text="National Identification Number (14 characters)"
    )

    is_approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    external_id = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        null=True,
        help_text="Public ID: Riders start with R001, Roadies with BS001",
    )

    is_active = models.BooleanField(default=True)
    is_online = models.BooleanField(default=False, editable=False)
    is_deleted = models.BooleanField(default=False)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, editable=False)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, editable=False)

    current_login_id = models.UUIDField(null=True, blank=True, help_text="Used to enforce single device login")

    services_selected = models.BooleanField(
        default=False,
        help_text="Tracks if roadie has selected services on first login"
    )

    trial_end_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="The date when the user's free trial expires."
    )

    @property
    def trial_days_left(self):
        """Returns the number of days left in the free trial, or 0 if expired/not applicable."""
        if not self.trial_end_date:
            return 0
        from django.utils import timezone
        diff = self.trial_end_date - timezone.now()
        total_seconds = diff.total_seconds()
        if total_seconds <= 0:
            return 0
        # diff.days returns floor, but we want to include today. 
        # For example, if 0.5 days left, it should show 1 day.
        return int(total_seconds // 86400) + 1

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        from django.utils import timezone
        
        # Lock in trial end date when they are APPROVED for the first time
        if not is_new and self.is_approved and not self.trial_end_date:
            try:
                # If trial_end_date is None, it means it hasn't started yet.
                # Setting it the first time they are approved ensures it starts 
                # only when they can actually use the platform.
                # Once set, it stays fixed even if the user is unapproved then re-approved.
                from django.apps import apps
                ConfigModel = apps.get_model('users', 'PlatformConfig')
                config = ConfigModel.objects.first()
                if config and config.trial_days > 0:
                    from datetime import timedelta
                    self.trial_end_date = timezone.now() + timedelta(days=config.trial_days)
            except Exception as e:
                import logging
                logging.error(f"Error setting trial date: {e}")

        if not self.external_id:
            if self.role == 'RIDER':
                prefix = 'R'
            elif self.role == 'RODIE':
                prefix = 'BS'
            elif self.role == 'MECHANIC':
                prefix = 'IT'
            else:
                prefix = None

            if prefix:
                try:
                    with transaction.atomic():
                        existing = User.objects.filter(
                            external_id__startswith=prefix,
                            external_id__regex=r'^' + re.escape(prefix) + r'\d+$'
                        ).values_list('external_id', flat=True)
                        
                        max_n = 0
                        for val in existing:
                            if not val:
                                continue
                            try:
                                n = int(val[len(prefix):])
                                if n > max_n:
                                    max_n = n
                            except (ValueError, IndexError):
                                continue
                        
                        seq = max_n + 1
                        self.external_id = f"{prefix}{seq:03d}"
                except Exception:
                    self.external_id = f"{prefix}001"

        if not self.referral_code:
            prefix = 'VX'
            try:
                with transaction.atomic():
                    existing = User.objects.filter(
                        referral_code__startswith=prefix,
                        referral_code__regex=r'^' + re.escape(prefix) + r'\d+$'
                    ).values_list('referral_code', flat=True)
                    
                    max_n = 0
                    for val in existing:
                        if not val:
                            continue
                        try:
                            n = int(val[len(prefix):])
                            if n > max_n:
                                max_n = n
                        except (ValueError, IndexError):
                            continue
                    
                    seq = max_n + 1
                    self.referral_code = f"{prefix}{seq:03d}"
            except Exception:
                self.referral_code = f"VX001"

        if self.role == 'ADMIN':
            self.is_approved = False

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.role})"


class RiderAvailabilityLog(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='availability_logs')
    went_online_at = models.DateTimeField()
    went_offline_at = models.DateTimeField(null=True, blank=True)

    def duration_seconds(self):
        if self.went_offline_at:
            return (self.went_offline_at - self.went_online_at).total_seconds()
        from django.utils import timezone
        return (timezone.now() - self.went_online_at).total_seconds()

    def __str__(self):
        return f"{self.user.username} online {self.went_online_at} - {self.went_offline_at or 'now'}"

    DEVICE_TYPE_CHOICES = (
        ('IOS', 'iOS'),
        ('ANDROID', 'Android'),
    )
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES, null=True, blank=True)


class Wallet(models.Model):
    """Simple wallet model to track V coins for users."""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"Wallet({self.user.username}): {self.balance}"


class Notification(models.Model):
    """In-app notification for users."""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    data = models.JSONField(blank=True, null=True)
    read = models.BooleanField(default=False)
    broadcast = models.BooleanField(default=False)
    TARGET_ROLE_CHOICES = (
        ('RIDER', 'Rider'),
        ('RODIE', 'Rodie'),
        ('MECHANIC','Mechanic')
    )
    target_role = models.CharField(max_length=10, choices=TARGET_ROLE_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification({self.user.username}): {self.title}"


class WalletTransaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.wallet.user.username}: {self.amount} ({self.reason})"


class Referral(models.Model):
    referrer = models.ForeignKey('users.User', related_name='referrals_made', on_delete=models.CASCADE)
    referred = models.ForeignKey('users.User', related_name='referred_by_user', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Referral {self.referrer.username} -> {self.referred.username}: {self.amount}"


class PlatformConfig(models.Model):
    """Singleton-like config to allow admin configuration via API.
    Admins can set `max_negative_balance` and `service_fee`.
    """
    max_negative_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    trial_days = models.IntegerField(default=0, help_text="Free trial period in days from user registration")
    mechanic_transition_documents = models.JSONField(default=list, help_text="List of required documents for mechanic transition, e.g. ['ID', 'License', 'Certificate']")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PlatformConfig(max_neg={self.max_negative_balance}, fee={self.service_fee})"


class Payment(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    )

    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reference = models.CharField(max_length=100, unique=True, help_text="Internal unique reference")
    processor_id = models.CharField(max_length=100, blank=True, null=True, help_text="Pesapal Order Tracking ID")
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.reference} ({self.status})"