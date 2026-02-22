import urllib.request
import urllib.error

url = 'http://127.0.0.1:8000/api/non_existent_url_to_trigger_404'

try:
    response = urllib.request.urlopen(url)
    print("Success (unexpected):", response.getcode())
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print("Saving response to debug_urls.html")
    with open('debug_urls.html', 'wb') as f:
        f.write(e.read())
except Exception as e:
    print(f"Error: {e}")
