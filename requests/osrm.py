import requests
import time

OSRM_ROUTE_URL = 'https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false&annotations=duration,distance'


def get_route_info(origin_lat, origin_lng, dest_lat, dest_lng, timeout=5):
    """Call OSRM and return (distance_meters, duration_seconds) or (None, None) on failure."""
    try:
        url = OSRM_ROUTE_URL.format(lon1=origin_lng, lat1=origin_lat, lon2=dest_lng, lat2=dest_lat)
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        routes = data.get('routes') or []
        if not routes:
            return None, None
        route = routes[0]
        distance = route.get('distance')  # meters
        duration = route.get('duration')  # seconds
        return distance, duration
    except Exception:
        return None, None
