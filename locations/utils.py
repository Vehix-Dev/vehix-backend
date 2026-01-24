import math


def calculate_distance_km(lat1, lng1, lat2, lng2):
    R = 6371  

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    dlat = lat2 - lat1
    dlng = math.radians(lng2 - lng1)

    a = math.sin(dlat / 2) ** 2 + \
        math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
