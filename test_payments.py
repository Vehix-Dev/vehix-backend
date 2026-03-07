#!/usr/bin/env python
"""
Test script to verify the payment system for roadies
Run with: python test_payments.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth import get_user_model
from users.models import Wallet, Payment, WalletTransaction
from decimal import Decimal
from django.db import models

User = get_user_model()

def test_payment_system():
    print("🧪 Testing Vehix Payment System for Roadies")
    print("=" * 50)
    
    # 1. Check if Pesapal config is set
    print("\n1. Checking Pesapal Configuration:")
    from django.conf import settings
    pesapal_config = {
        'PESAPAL_URL': getattr(settings, 'PESAPAL_URL', 'NOT SET'),
        'PESAPAL_CONSUMER_KEY': 'SET' if getattr(settings, 'PESAPAL_CONSUMER_KEY', '') else 'NOT SET',
        'PESAPAL_CONSUMER_SECRET': 'SET' if getattr(settings, 'PESAPAL_CONSUMER_SECRET', '') else 'NOT SET',
        'PESAPAL_IPN_ID': 'SET' if getattr(settings, 'PESAPAL_IPN_ID', '') else 'NOT SET',
    }
    
    for key, value in pesapal_config.items():
        status = "✅" if value != 'NOT SET' else "❌"
        print(f"   {status} {key}: {value}")
    
    # 2. Create or get a test roadie user
    print("\n2. Setting up test roadie user:")
    roadie, created = User.objects.get_or_create(
        username='test_roadie',
        defaults={
            'email': 'test@roadie.com',
            'phone': '256700123456',
            'first_name': 'Test',
            'last_name': 'Roadie',
            'role': 'RODIE',
            'is_approved': True
        }
    )
    if created:
        roadie.set_password('testpass123')
        roadie.save()
        print("   ✅ Created new test roadie user")
    else:
        print("   ✅ Using existing test roadie user")
    
    # 3. Check wallet
    print("\n3. Checking wallet:")
    wallet, created = Wallet.objects.get_or_create(user=roadie)
    print(f"   Wallet ID: {wallet.id}")
    print(f"   Current Balance: UGX {wallet.balance}")
    
    # 4. Test payment creation
    print("\n4. Testing payment creation:")
    import uuid
    reference = f"TEST-{uuid.uuid4().hex[:12].upper()}"
    
    payment = Payment.objects.create(
        user=roadie,
        amount=Decimal('1000.00'),
        transaction_type='DEPOSIT',
        status='PENDING',
        reference=reference,
        description="Test deposit payment"
    )
    print(f"   ✅ Created test payment: {reference}")
    
    # 5. Test wallet transaction
    print("\n5. Testing wallet transaction:")
    transaction = WalletTransaction.objects.create(
        wallet=wallet,
        amount=Decimal('500.00'),
        reason="Test transaction"
    )
    print(f"   ✅ Created test transaction: {transaction.reason}")
    
    # 6. Test payment status view data
    print("\n6. Testing payment serialization:")
    from users.serializers import PaymentSerializer, WalletSerializer, TransactionHistorySerializer
    
    payment_serializer = PaymentSerializer(payment)
    wallet_serializer = WalletSerializer(wallet)
    
    print(f"   Payment data: {payment_serializer.data}")
    print(f"   Wallet data: {wallet_serializer.data}")
    
    # 7. Test roadie payments endpoint data
    print("\n7. Testing roadie payments summary:")
    payments = Payment.objects.filter(user=roadie).order_by('-created_at')
    transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')
    
    combined = list(payments) + list(transactions)
    combined.sort(key=lambda x: x.created_at, reverse=True)
    
    history_serializer = TransactionHistorySerializer(combined, many=True)
    
    total_deposits = payments.filter(
        transaction_type='DEPOSIT',
        status='COMPLETED'
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    summary = {
        'current_balance': wallet.balance,
        'total_earned': total_deposits,
        'transaction_count': len(combined)
    }
    print(f"   Summary: {summary}")
    
    print("\n" + "=" * 50)
    print("✅ Payment system test completed successfully!")
    print("📝 Next steps:")
    print("   1. Set up Pesapal credentials in .env file")
    print("   2. Test deposit flow via roadie app")
    print("   3. Test withdrawal flow via roadie app")
    print("   4. Verify IPN callbacks work correctly")

if __name__ == '__main__':
    test_payment_system()
