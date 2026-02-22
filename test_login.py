import urllib.request
import json

url = 'http://127.0.0.1:8000/api/login/'
data = {
    'username': '+256700000000',
    'password': 'testpassword123'
}

try:
    req = urllib.request.Request(url)
    req.add_header('Content-Type', 'application/json')
    jsondata = json.dumps(data)
    jsondataasbytes = jsondata.encode('utf-8')
    req.add_header('Content-Length', len(jsondataasbytes))
    
    response = urllib.request.urlopen(req, jsondataasbytes)
    print(f"Status Code: {response.getcode()}")
    print(f"Response Body: {response.read().decode('utf-8')}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(f"Response Body: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
