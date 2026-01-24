import sys
import os
original_path = sys.path[:]
if os.getcwd() in sys.path: sys.path.remove(os.getcwd())
if '.' in sys.path: sys.path.remove('.')
import requests
sys.path = original_path
import json

BASE_URL = 'https://pay.pesapal.com/v3'
CONSUMER_KEY = 'hezvEw5rc1nMNtfIZ0D4yVmHSAbV4VDw'
CONSUMER_SECRET = 'Ay7z5caeDyKyqim8M7NuR9MjGU4='

url = f"{BASE_URL}/api/Auth/RequestToken"
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}
payload = {
    "consumer_key": CONSUMER_KEY,
    "consumer_secret": CONSUMER_SECRET
}

print(f"Testing direct request to {url}")
try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Request Exception: {e}")

# Try Sandbox just in case
SANDBOX_URL = 'https://cybqa.pesapal.com/pesapalv3'
print(f"\nTesting direct request to {SANDBOX_URL}/api/Auth/RequestToken")
try:
    response = requests.post(f"{SANDBOX_URL}/api/Auth/RequestToken", json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Request Exception: {e}")
