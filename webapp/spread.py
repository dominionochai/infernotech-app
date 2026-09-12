import math
from weather import degrees_to_compass

EARTH_RADIUS_KM = 6371
SPREAD_FACTOR = 0.15
PROJECTION_HOURS = 3
CONE_HALF_ANGLE_DEG = 25


def destination_point(lat, lon, bearing_deg, distance_km):
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    brng = math.radians(bearing_deg)
    d_r = distance_km / EARTH_RADIUS_KM
    lat2 = math.asin(math.sin(lat1) * math.cos(d_r) + math.cos(lat1) * math.sin(d_r) * math.cos(brng))
    lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(d_r) * math.cos(lat1),
                              math.cos(d_r) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


def project_spread(lat, lon, wind):
    speed = wind.get("wind_speed_kmh")
    wind_from = wind.get("wind_direction_deg")
    if not speed or wind_from is None:
        return None

    push_dir = (wind_from + 180) % 360
    distance_km = round(speed * SPREAD_FACTOR * PROJECTION_HOURS, 2)
    if distance_km <= 0:
        return None

    left_lat, left_lon = destination_point(lat, lon, (push_dir - CONE_HALF_ANGLE_DEG) % 360, distance_km)
    right_lat, right_lon = destination_point(lat, lon, (push_dir + CONE_HALF_ANGLE_DEG) % 360, distance_km)
    tip_lat, tip_lon = destination_point(lat, lon, push_dir, distance_km)

    return {
        "push_direction_deg": round(push_dir, 1),
        "push_direction_compass": degrees_to_compass(push_dir),
        "wind_speed_kmh": speed,
        "distance_km": distance_km,
        "hours": PROJECTION_HOURS,
        "polygon": [[lon, lat], [left_lon, left_lat], [tip_lon, tip_lat], [right_lon, right_lat], [lon, lat]],
    }
