from django.db import models
from django.conf import settings


class RodieLocation(models.Model):
    rodie = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'RODIE'}
    )
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.rodie.username} @ {self.lat},{self.lng}"
