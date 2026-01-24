from django.db import models
from django.conf import settings


class ChatMessage(models.Model):
    service_request = models.ForeignKey('requests.ServiceRequest', on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ChatMessage(req={self.service_request_id}, sender={self.sender_id})"
