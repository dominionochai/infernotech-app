"""
Live, worldwide wildfire data — not limited to the Attica sample.

  - Open-Meteo Geocoding API for turning a place name into lat/lon.
    (Nominatim/OpenStreetMap was used originally, but its domain is blocked
    on some networks/firewalls -- Open-Meteo covers the same need without
    that issue.)
  - NASA FIRMS Area API for near-real-time satellite fire hotspots
    (VIIRS/MODIS) anywhere on Earth, updated within ~3 hours of overpass.
    Requires a free MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/area/
    (set it as the FIRMS_MAP_KEY environment variable).
"""
import csv
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FIRMS_AREA_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
USER_AGENT = "stemist-wildfire-recovery-map/1.0 (hackathon demo)"


class FireDataError(Exception):
    pass


def geocode_place(place):
    """Returns (lat, lon, display_name) for a free-text place name.
    Works best with a specific city/town name rather than a bare
    state/country name."""
    params = urllib.parse.urlencode({"name": place, "count": 1, "language": "en", "format": "json"})
    req = urllib.request.Request(f"{GEOCODE_URL}?{params}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        raise FireDataError(f"Could not geocode '{place}': {e}")

    results = data.get("results")
    if not results:
        raise FireDataError(f"No location found for '{place}'. Try a specific city or town name.")

    r = results[0]
    parts = [r.get("name"), r.get("admin1"), r.get("country")]
    display_name = ", ".join(p for p in parts if p)
    return float(r["latitude"]), float(r["longitude"]), display_name or place


def fetch_firms_hotspots(lat, lon, days=1, radius_deg=0.6, source="VIIRS_SNPP_NRT"):
    map_key = os.environ.get("FIRMS_MAP_KEY")
    if not map_key:
        raise FireDataError(
            "No FIRMS_MAP_KEY set. Get a free key at "
            "https://firms.modaps.eosdis.nasa.gov/api/area/ and set it as "
            "the FIRMS_MAP_KEY environment variable."
        )

    days = max(1, min(int(days), 5))
    west, south = lon - radius_deg, lat - radius_deg
    east, north = lon + radius_deg, lat + radius_deg
    bbox = f"{west},{south},{east},{north}"

    url = f"{FIRMS_AREA_URL}/{map_key}/{source}/{bbox}/{days}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise FireDataError(f"NASA FIRMS request failed: {e}")

    if body.strip().lower().startswith(("invalid", "error", "<!doctype", "<html")):
        raise FireDataError(f"NASA FIRMS returned an error: {body[:200]}")

    reader = csv.DictReader(io.StringIO(body))
    hotspots = []
    for row in reader:
        try:
            hotspots.append({
                "lat": float(row["latitude"]),
                "lon": float(row["longitude"]),
                "brightness": float(row.get("bright_ti4") or row.get("brightness") or 0),
                "confidence": row.get("confidence", "n/a"),
                "frp": float(row.get("frp", 0) or 0),
                "acq_date": row.get("acq_date", ""),
                "acq_time": row.get("acq_time", ""),
            })
        except (KeyError, ValueError):
            continue

    return hotspots


def hotspots_to_geojson(hotspots):
    features = []
    for h in hotspots:
        features.append({
            "type": "Feature",
            "properties": {"brightness": h["brightness"], "confidence": h["confidence"],
                            "frp": h["frp"], "acq_date": h["acq_date"], "acq_time": h["acq_time"]},
            "geometry": {"type": "Point", "coordinates": [h["lon"], h["lat"]]},
        })
    return {"type": "FeatureCollection", "features": features}
