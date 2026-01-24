import sys
import os

# Identify the project root
project_root = r"c:\Users\tutum\Downloads\JOINED PROJECT\vehix-backend\config"
sys.path.append(project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from users.pesapal import PesapalClient

client = PesapalClient()
print(f"Testing with BASE_URL: {client.BASE_URL}")
print(f"Consumer Key: {client.CONSUMER_KEY}")
token = client.get_token()

if token:
    print(f"SUCCESS! Token: {token[:10]}...")
else:
    print("FAILED to get token. See details above.")
