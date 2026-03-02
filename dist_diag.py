import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import User
from services.models import ServiceType, RodieService
from requests.models import ServiceRequest
from locations.utils import calculate_distance_km

def final_check():
    req = ServiceRequest.objects.all().order_by('-created_at').first()
    if not req:
        print("No requests found.")
        return

    print(f"Latest Request ID: {req.id}, Service: {req.service_type.name}, Lat: {req.rider_lat}, Lng: {req.rider_lng}")
    
    rodie = User.objects.filter(role='RODIE').first()
    if not rodie:
        print("No Roadies found.")
        return
    
    # Check Rodie location sources
    from locations.models import RodieLocation
    rl = RodieLocation.objects.filter(rodie=rodie).first()
    
    print(f"Roadie: {rodie.username}, User Lat/Lng: {rodie.lat}/{rodie.lng}, RodieLocation: {rl.lat if rl else 'None'}/{rl.lng if rl else 'None'}")
    
    lat = rl.lat if rl else rodie.lat
    lng = rl.lng if rl else rodie.lng
    
    if lat and lng:
        dist = calculate_distance_km(float(req.rider_lat), float(req.rider_lng), float(lat), float(lng))
        print(f"Distance: {dist} km")
        if dist > 4.0:
            print("ALERT: Distance is greater than 4km (MAX_DISTANCE_KM). Matching will fail.")
        else:
            print("Distance is within 4km. Matching SHOULD work.")
    else:
        print("ALERT: Roadie has no location data.")

if __name__ == "__main__":
    final_check()
