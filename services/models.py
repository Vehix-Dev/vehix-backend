from django.db import models
from django.conf import settings
from django.utils import timezone


class ServiceType(models.Model):
    CATEGORY_CHOICES = (
        ('BASIC', 'Basic'),
        ('MECHANIC', 'Mechanic'),
    )

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default='BASIC')
    fixed_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    image = models.ImageField(upload_to='services/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class RodieService(models.Model):
    rodie = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role__in': ['RODIE', 'MECHANIC']}
    )

    service = models.ForeignKey(
        ServiceType,
        on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ('rodie', 'service')

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.rodie.username} - {self.service}"
