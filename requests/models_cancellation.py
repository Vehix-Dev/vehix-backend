from django.db import models
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
        'requests.ServiceRequest',
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
