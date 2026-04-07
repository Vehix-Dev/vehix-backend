from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Rating(models.Model):
    """Rating model for service requests - riders rate roadies and vice versa"""
    
    service_request = models.ForeignKey(
        'requests.ServiceRequest',
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ratings_given'
    )
    
    rated_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ratings_received'
    )
    
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    
    comment = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('service_request', 'rater')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service_request', 'rater']),
            models.Index(fields=['rated_user', '-created_at']),
        ]
    
    def __str__(self):
        return f"Rating({self.rater.username} → {self.rated_user.username}: {self.rating}★)"
    
    def save(self, *args, **kwargs):
        # Auto-set rated_user based on rater role using IDs for reliability
        if not self.rated_user_id:
            if self.rater_id == self.service_request.rider_id:
                self.rated_user_id = self.service_request.rodie_id
            elif self.rater_id == self.service_request.rodie_id:
                self.rated_user_id = self.service_request.rider_id
        super().save(*args, **kwargs)
