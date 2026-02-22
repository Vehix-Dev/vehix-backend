import os
import django
import sys

# Add project root to path
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    django.setup()
    print("Django setup successful.")
    
    print("Importing users.tokens...")
    from users import tokens
    print("users.tokens imported successfully.")
    
    print("Importing users.urls...")
    from users import urls
    print("users.urls imported successfully.")
    
except Exception as e:
    print(f"Error: {e}")
