import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

class ResendEmailBackend(BaseEmailBackend):
    """
    A custom email backend for Resend using their REST API.
    Avoids SMTP port blocking issues.
    """
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        self.api_url = "https://api.resend.com/emails"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                payload = {
                    "from": message.from_email,
                    "to": message.to,
                    "subject": message.subject,
                    "html": message.body if message.content_subtype == 'html' else None,
                    "text": message.body if message.content_subtype != 'html' else None,
                }
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                response = requests.post(self.api_url, json=payload, headers=headers)
                if response.status_code in [200, 201]:
                    sent_count += 1
                else:
                    if not self.fail_silently:
                        print(f"Resend API Error: {response.status_code} - {response.text}")
            except Exception as e:
                if not self.fail_silently:
                    print(f"Resend Backend Exception: {e}")
        
        return sent_count
