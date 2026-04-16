import requests
import time

OSRM_ROUTE_URL = 'https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false&annotations=duration,distance'


def get_route_info(origin_lat, origin_lng, dest_lat, dest_lng, timeout=3):
    """Call OSRM and return (distance_meters, duration_seconds) or fallback estimation on failure."""
    try:
        # 1. Attempt OSRM real-road calculation
        url = OSRM_ROUTE_URL.format(lon1=origin_lng, lat1=origin_lat, lon2=dest_lng, lat2=dest_lat)
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            routes = data.get('routes') or []
            if routes:
                route = routes[0]
                return route.get('distance'), route.get('duration')
    except Exception:
        pass
    
    # 2. Fallback: Straight-line (Haversine) with Circuity Factor & Avg Speed
    # In cities like Kampala, road distance is approx 1.4x straight line.
    # Avg speed for Bodas/Vehix is roughly 20km/h.
    try:
        from math import radians, cos, sin, asin, sqrt
        lon1, lat1, lon2, lat2 = map(radians, [float(origin_lng), float(origin_lat), float(dest_lng), float(dest_lat)])
        dlon = lon2 - lon1 
        dlat = lat2 - lat1 
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a)) 
        km = 6371 * c
        
        # Adjust for road circuity (1.4x)
        road_km = km * 1.4
        distance_m = road_km * 1000
        
        # Duration: road_km / avg_speed_kmh (20 km/h) converted to seconds
        duration_s = (road_km / 20.0) * 3600
        
        return distance_m, duration_s
    except Exception:
        return None, None
