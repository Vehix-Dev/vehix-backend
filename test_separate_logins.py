import urllib.request
import json

base_url = 'http://127.0.0.1:8000/api'
rider_login_url = f'{base_url}/login/rider/'
roadie_login_url = f'{base_url}/login/roadie/'

# Test Data
# Assuming testrider exists from previous steps (role=RIDER)
# You might need to create a testroadie
rider_creds = {'username': '+256700000000', 'password': 'testpassword123'}
roadie_creds = {'username': '+256750000000', 'password': 'testpassword123'} # Will try to create if not exists

def login(url, creds, name):
    print(f"--- {name} Login Test ({url}) ---")
    try:
        req = urllib.request.Request(url)
        req.add_header('Content-Type', 'application/json')
        jsondata = json.dumps(creds).encode('utf-8')
        req.add_header('Content-Length', len(jsondata))
        
        response = urllib.request.urlopen(req, jsondata)
        print(f"Success! Status: {response.getcode()}")
        data = json.loads(response.read().decode('utf-8'))
        print(f"Token received: {data.get('access')[:20]}...")
    except urllib.error.HTTPError as e:
        print(f"Failed! Status: {e.code}")
        print(f"Response: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Error: {e}")
    print("\n")

# Create Roadie user first just in case
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
try:
    if not User.objects.filter(phone='+256750000000').exists():
        User.objects.create_user(username='testroadie', phone='+256750000000', password='testpassword123', role='RODIE')
        print("Created test roadie user.")
except Exception as e:
    print(f"Could not create roadie: {e}")


# Run Tests
# 1. Successful Rider Login
login(rider_login_url, rider_creds, "Valid Rider")

# 2. Successful Roadie Login
login(roadie_login_url, roadie_creds, "Valid Roadie")

# 3. Rider trying to log in as Roadie (Should Fail)
login(roadie_login_url, rider_creds, "Rider on Roadie Setup")

# 4. Roadie trying to log in as Rider (Should Fail)
login(rider_login_url, roadie_creds, "Roadie on Rider Setup")
