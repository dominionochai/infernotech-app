"""
InfernoTech — Unified Wildfire Response Platform
Submission for "Fund My Crazy by Google" — Community & Living theme.

Three real, independently-verifiable layers merged into one system:

  1. SATELLITE DETECTION (this app): live NASA FIRMS hotspots worldwide,
     wind-based spread projection, address-level pre-disaster risk scoring,
     Gemini-powered plain-language briefs. Falls back to the original
     Attica, Greece case study if no place is searched or an API call fails.

  2. GROUND CONFIRMATION (Ridgeline, github.com/ayaan-gupta/ridgeline, run
     as a sibling service via docker-compose): watches public wildfire
     lookout cameras and confirms a detection only after 3 consecutive
     frames score above threshold. InfernoTech polls its documented
     GET /api/detections endpoint (ridgeline_client.py) and overlays
     confirmed detections on the map — higher trust, narrower coverage,
     complementing satellite's broad-but-noisier view.

  3. CARBON-CREDIT FINANCING (Hedera Guardian, github.com/hashgraph/guardian,
     run separately — a full platform, not embedded here): when a searched
     area represents protected forest with avoided deforestation, this app
     can submit a real MRV document to a running Guardian instance's
     external-data API under the VM0015 "Avoided Unplanned Deforestation"
     policy (guardian_client.py) — ties wildfire prevention to actual
     carbon-market financing, verifiable on the Hedera public ledger.

Ridgeline and Guardian are both large, real, separately-run systems — this
app talks to them through their documented public APIs (ridgeline_client.py,
guardian_client.py) rather than re-implementing any of their internals.
Both integrations degrade gracefully: if RIDGELINE_API_URL or
GUARDIAN_API_URL/GUARDIAN_OWNER_DID aren't set, or either service isn't
reachable, InfernoTech keeps working exactly as before with those layers
simply absent — same fallback discipline as fire_data.py/weather.py.
"""
import json
import os
import urllib.error
import urllib.request

import folium
from flask import Flask, jsonify, render_template, request

import fire_data
import guardian_client
import ridgeline_client
import risk
import spread
import weather
from color import cat, green, pink, purple, red, yellow

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

ATTICA_CENTER = [37.782953, 23.942564]

# Esri's free satellite imagery basemap, a separate domain from both
# OpenStreetMap's tile servers (blocked on some networks) and CartoDB's
# (now requires an API key for their free tiles). No key required.
BASE_TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
BASE_TILES_ATTR = "Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community"
LABELS_TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
LABELS_TILES_ATTR = "Labels &copy; Esri"

ATTICA_LAYERS = [
    ("copernicus_burnt.geojson", "Copernicus observed burn area", purple),
    ("buildings.geojson", "Buildings", red),
    ("natural_landcover.geojson", "Natural / agricultural landcover", cat),
    ("fireclr_mask.geojson", "FireCLR burn mask", pink),
    ("sam_mask.geojson", "SAMGeo burn mask", green),
    ("diff_clr.geojson", "Copernicus vs FireCLR difference", yellow),
    ("diff_sam.geojson", "Copernicus vs SAMGeo difference", yellow),
]


def load_layer(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path) as f:
        return json.load(f)


def shoelace_area_km2(coords):
    lat0 = sum(c[1] for c in coords) / len(coords)
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * abs(__import__("math").cos(__import__("math").radians(lat0)))
    pts = [(c[0] * km_per_deg_lon, c[1] * km_per_deg_lat) for c in coords]
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def attica_stats():
    stats = {}
    for filename, name, _ in ATTICA_LAYERS:
        data = load_layer(filename)
        total = 0.0
        for feat in data["features"]:
            geom = feat["geometry"]
            if geom["type"] == "Polygon":
                total += shoelace_area_km2(geom["coordinates"][0])
        stats[name] = round(total, 2)
    return stats


def add_ridgeline_layer(m):
    """Best-effort overlay of Ridgeline ground-camera-confirmed detections.
    Silently skipped if RIDGELINE_API_URL isn't set or unreachable — this
    layer is a bonus, never a blocker."""
    try:
        detections = ridgeline_client.fetch_recent_detections(limit=50)
    except ridgeline_client.RidgelineError:
        return None

    if not detections:
        return 0

    fg = folium.FeatureGroup(name=f"Ridgeline camera-confirmed ({len(detections)})")
    for d in detections:
        folium.Marker(
            [d["lat"], d["lon"]],
            tooltip=f"{d['camera_name']} — {d['verdict']}",
            popup=(
                f"Camera: {d['camera_name']}<br>Confidence: {d.get('confidence')}<br>"
                f"Confirmed: {d.get('confirmed_at')}<br>Verdict: {d['verdict']}"
            ),
            icon=folium.Icon(color="darkred", icon="camera", prefix="fa"),
        ).add_to(fg)
    fg.add_to(m)
    return len(detections)


def build_attica_map():
    m = folium.Map(location=ATTICA_CENTER, zoom_start=12, tiles=BASE_TILES, attr=BASE_TILES_ATTR)
    folium.TileLayer(tiles=LABELS_TILES, attr=LABELS_TILES_ATTR, name="Labels", overlay=True, control=False).add_to(m)
    for filename, name, style_fn in ATTICA_LAYERS:
        data = load_layer(filename)
        folium.GeoJson(data, style_function=style_fn, name=name).add_to(m)
    add_ridgeline_layer(m)
    folium.LayerControl().add_to(m)
    return m


def build_hotspot_map(lat, lon, hotspots, display_name, projection):
    m = folium.Map(location=[lat, lon], zoom_start=9, tiles=BASE_TILES, attr=BASE_TILES_ATTR)
    folium.TileLayer(tiles=LABELS_TILES, attr=LABELS_TILES_ATTR, name="Labels", overlay=True, control=False).add_to(m)
    folium.Marker(
        [lat, lon], tooltip=display_name, icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)

    fg = folium.FeatureGroup(name=f"Active fire hotspots ({len(hotspots)})")
    for h in hotspots:
        frp = h["frp"] or 0
        radius = 4 + min(frp / 20, 12)
        folium.CircleMarker(
            location=[h["lat"], h["lon"]], radius=radius, color="#ff4d2e", fill=True,
            fill_color="#ff8a5c", fill_opacity=0.75,
            popup=f"FRP: {frp:.1f} MW<br>Confidence: {h['confidence']}<br>Detected: {h['acq_date']} {h['acq_time']}",
        ).add_to(fg)
    fg.add_to(m)

    if projection:
        ring = [[lat_lon[1], lat_lon[0]] for lat_lon in projection["polygon"]]
        folium.Polygon(
            locations=ring, color="#ffb020", weight=2, fill=True, fill_color="#ffb020", fill_opacity=0.18,
            tooltip=(
                f"Projected spread heuristic: wind {projection['wind_speed_kmh']} km/h toward "
                f"{projection['push_direction_compass']}, ~{projection['distance_km']} km over "
                f"{projection['hours']}h (rough estimate, not a validated fire model)"
            ),
        ).add_to(m)

    ridgeline_count = add_ridgeline_layer(m)
    folium.LayerControl().add_to(m)
    return m, ridgeline_count


def get_primary_hotspot(hotspots):
    if not hotspots:
        return None
    return max(hotspots, key=lambda h: h["frp"] or 0)


def get_map_context(place, days):
    if not place:
        m = build_attica_map()
        return m.get_root().render(), attica_stats(), {
            "mode": "demo",
            "location": "Attica, Greece (July 2023 wildfires — bundled demo data)",
        }

    try:
        lat, lon, display_name = fire_data.geocode_place(place)
        hotspots = fire_data.fetch_firms_hotspots(lat, lon, days=days)
    except fire_data.FireDataError as e:
        m = build_attica_map()
        return m.get_root().render(), attica_stats(), {
            "mode": "fallback",
            "location": "Attica, Greece (fallback demo data)",
            "error": str(e),
        }

    stats = {
        "Active fire hotspots detected": len(hotspots),
        "Combined fire radiative power (MW)": round(sum(h["frp"] for h in hotspots), 1),
        "Days of data searched": days,
    }

    projection = None
    wind = None
    primary = get_primary_hotspot(hotspots)
    if primary:
        try:
            wind = weather.fetch_current_weather(primary["lat"], primary["lon"])
            stats["Wind at strongest hotspot"] = (
                f"{wind['wind_speed_kmh']} km/h from the {weather.degrees_to_compass(wind['wind_direction_deg'])}"
            )
            projection = spread.project_spread(primary["lat"], primary["lon"], wind)
            if projection:
                stats["Projected spread (heuristic)"] = (
                    f"~{projection['distance_km']} km toward the {projection['push_direction_compass']} "
                    f"over next {projection['hours']}h"
                )
        except weather.WeatherError:
            pass

    m, ridgeline_count = build_hotspot_map(lat, lon, hotspots, display_name, projection)
    if ridgeline_count:
        stats["Ridgeline camera-confirmed detections"] = ridgeline_count

    meta = {"mode": "live", "location": display_name, "hotspot_count": len(hotspots)}
    if wind and wind.get("wind_direction_deg") is not None:
        meta["wind_direction_deg"] = wind["wind_direction_deg"]
        meta["wind_speed_kmh"] = wind["wind_speed_kmh"]
    if ridgeline_count:
        meta["ridgeline_count"] = ridgeline_count
    return m.get_root().render(), stats, meta


@app.route("/")
def base():
    place = request.args.get("place", "").strip()
    days = request.args.get("days", "1")
    try:
        days = int(days)
    except ValueError:
        days = 1

    map_html, stats, meta = get_map_context(place, days)
    return render_template("index.html", map_html=map_html, stats=stats, meta=meta, place=place, days=days)


@app.route("/api/community-brief", methods=["POST"])
def community_brief():
    payload = request.get_json(silent=True) or {}
    place = (payload.get("place") or "").strip()
    days = payload.get("days") or 1
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 1

    _, stats, meta = get_map_context(place, days)
    brief = generate_gemini_brief(stats, meta)
    return jsonify({"brief": brief, "meta": meta})


@app.route("/api/risk-check", methods=["POST"])
def risk_check():
    payload = request.get_json(silent=True) or {}
    address = (payload.get("address") or "").strip()
    if not address:
        return jsonify({"error": "Enter an address or place name."}), 400

    try:
        lat, lon, display_name = fire_data.geocode_place(address)
    except fire_data.FireDataError as e:
        return jsonify({"error": str(e)}), 400

    try:
        wx = weather.fetch_current_weather(lat, lon)
    except weather.WeatherError as e:
        return jsonify({"error": str(e)}), 502

    nearby_fire_count = None
    try:
        nearby = fire_data.fetch_firms_hotspots(lat, lon, days=1, radius_deg=0.27)
        nearby_fire_count = len(nearby)
    except fire_data.FireDataError:
        pass

    score, label, reasons = risk.compute_risk_score(wx, nearby_fire_count)
    blurb = generate_risk_blurb(display_name, wx, score, label, reasons)

    return jsonify({
        "location": display_name, "score": score, "label": label,
        "reasons": reasons, "weather": wx, "blurb": blurb,
    })


@app.route("/api/ridgeline-status", methods=["GET"])
def ridgeline_status():
    """Lets the UI show whether Ridgeline is actually wired up and reachable."""
    try:
        detections = ridgeline_client.fetch_recent_detections(limit=5)
        return jsonify({"connected": True, "recent_count": len(detections)})
    except ridgeline_client.RidgelineError as e:
        return jsonify({"connected": False, "error": str(e)})


@app.route("/api/guardian-mrv", methods=["POST"])
def guardian_mrv():
    """Submits a VM0015 avoided-deforestation MRV document to a running
    Guardian instance for the searched/checked area. Requires
    GUARDIAN_API_URL and GUARDIAN_OWNER_DID to be set to a real, already-
    configured Guardian instance with VM0015 imported — see guardian_client.py."""
    payload = request.get_json(silent=True) or {}
    location_name = (payload.get("location_name") or "").strip()
    lat = payload.get("lat")
    lon = payload.get("lon")
    protected_area_ha = payload.get("protected_area_ha")
    monitoring_start = payload.get("monitoring_start")
    monitoring_end = payload.get("monitoring_end")
    evidence_source = payload.get("evidence_source", "InfernoTech satellite + Ridgeline camera cross-check")

    if not all([location_name, lat is not None, lon is not None, protected_area_ha, monitoring_start, monitoring_end]):
        return jsonify({"error": "location_name, lat, lon, protected_area_ha, monitoring_start, monitoring_end are all required."}), 400

    document = guardian_client.build_vm0015_mrv_document(
        location_name, lat, lon, protected_area_ha, monitoring_start, monitoring_end, evidence_source
    )
    try:
        result = guardian_client.submit_mrv(document)
    except guardian_client.GuardianError as e:
        return jsonify({"error": str(e), "document": document}), 502

    return jsonify({"submitted": True, "result": result, "document": document})


def call_gemini(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("no GEMINI_API_KEY set")

    model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error {e.code}: {body_text[:500]}")
    return result["candidates"][0]["content"]["parts"][0]["text"]


def generate_gemini_brief(stats, meta):
    location = meta.get("location", "the searched area")
    prompt = (
        f"You are helping a local community and disaster-response officials near {location} understand "
        f"wildfire data in plain language. Given this data: {json.dumps(stats)}. "
        "Write a short (4-6 sentence) plain-language brief covering: what the numbers suggest about current "
        "fire activity, what that means for residents in the next few days, and one practical precaution or "
        "recovery recommendation. Avoid jargon. If this looks like historical/demo data rather than a live "
        "active fire, say so plainly instead of implying there is danger right now. If a 'Projected spread' "
        "figure is present, mention it is a rough estimate and residents should follow official guidance, not "
        "this app, for evacuation decisions. If 'Ridgeline camera-confirmed detections' is present, mention "
        "that ground cameras have independently confirmed activity, which raises confidence beyond satellite alone."
    )
    try:
        return call_gemini(prompt)
    except Exception as e:
        return (
            "[Offline demo brief — set GEMINI_API_KEY to enable live Gemini output] "
            f"Based on the current data for {location}: {json.dumps(stats)}. Residents nearby should follow "
            "official local guidance, keep an eye on air-quality advisories, and have an evacuation plan ready "
            "if hotspot activity is currently detected. For recovery planning after a fire, prioritizing "
            f"cropland and built-up areas closest to the burn perimeter tends to matter most. (reason: {e})"
        )


def generate_risk_blurb(location, wx, score, label, reasons):
    prompt = (
        f"You are a wildfire-preparedness assistant. For {location}, a simplified heuristic (not an official "
        f"fire-danger rating) scored current wildfire-weather risk as {score}/100 ({label}), based on: "
        f"{'; '.join(reasons)}. In 2-3 short sentences, explain what this suggests in plain language and give "
        "one practical preparation step. Explicitly note this is a simplified estimate, not an official rating, "
        "and that residents should check official local fire authority sources for real guidance."
    )
    try:
        return call_gemini(prompt)
    except Exception:
        return (
            f"[Offline demo note] {label} risk ({score}/100) for {location} based on current weather and "
            "nearby fire activity. This is a simplified estimate, not an official fire-danger rating — check "
            "your local fire authority for real guidance. A sensible precaution at this level: keep an "
            "emergency go-bag ready and know your evacuation route."
        )


if __name__ == "__main__":
    app.run(debug=True)
