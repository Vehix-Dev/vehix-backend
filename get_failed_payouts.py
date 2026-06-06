import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import Payment

print("--- RECENT WITHDRAWALS ---")
payments = Payment.objects.filter(transaction_type='WITHDRAWAL').order_by('-id')[:5]
for p in payments:
    print(f"Reference: {p.reference}")
    print(f"Amount: {p.amount}")
    print(f"Status: {p.status}")
    print(f"Description: {p.description}")
    print("-" * 40)
