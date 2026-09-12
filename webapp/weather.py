import json
import urllib.error
import urllib.parse
import urllib.request

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "stemist-wildfire-recovery-map/1.0 (hackathon demo)"


class WeatherError(Exception):
    pass


def fetch_current_weather(lat, lon):
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m",
    })
    req = urllib.request.Request(f"{FORECAST_URL}?{params}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        detail = str(e) or "no further detail — likely a network timeout, try again"
        raise WeatherError(f"Could not fetch weather ({type(e).__name__}): {detail}")

    current = data.get("current")
    if not current:
        raise WeatherError("Weather response missing 'current' data.")

    return {
        "temperature_c": current.get("temperature_2m"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "wind_direction_deg": current.get("wind_direction_10m"),
    }


COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def degrees_to_compass(deg):
    if deg is None:
        return "unknown"
    idx = round(deg / 22.5) % 16
    return COMPASS[idx]
