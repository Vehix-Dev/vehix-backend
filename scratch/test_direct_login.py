import os
import sys
import django
import uuid

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
try:
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    sys.exit(1)

from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()

def test_custom_login(username_input, password, target_role):
    print(f"\n--- Testing custom login logic for {target_role}: '{username_input}' ---")
    
    role_filter = {'role': target_role} if target_role else {}
    
    # 1. Exact match logic used in our proposed fix
    user_obj = User.objects.filter(username=username_input, **role_filter).first()
    if not user_obj:
        user_obj = User.objects.filter(email__iexact=username_input, **role_filter).first()
    if not user_obj:
        user_obj = User.objects.filter(phone=username_input, **role_filter).first()
        
    if not user_obj:
        print("❌ FAILED: User not found with given criteria.")
        return False
        
    print(f"✅ Found User: {user_obj.username} (Ext ID: {user_obj.external_id})")
    
    # 2. Check password
    if not user_obj.check_password(password):
        print("❌ FAILED: Incorrect password.")
        return False
        
    print("✅ Password matched.")
    
    # 3. Check active
    if not user_obj.is_active:
        print("❌ FAILED: Account is not active.")
        return False
        
    print("✅ Account is active. Login successful!")
    return True

if __name__ == "__main__":
    # Get a real user to test with from the DB
    test_user = User.objects.first()
    if test_user:
        print(f"Using test user: {test_user.username} has role {test_user.role}")
        print("Make sure you provide the correct password below to test the logic.\n")
        
        # Test with the username
        test_custom_login(test_user.username, 'testpassword123', test_user.role)
        # Test with the phone
        if test_user.phone:
            test_custom_login(test_user.phone, 'testpassword123', test_user.role)
        # Test with the email
        if test_user.email:
            test_custom_login(test_user.email, 'testpassword123', test_user.role)
    else:
        print("No users found in database!")
