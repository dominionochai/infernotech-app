"""
Client for Ridgeline (github.com/ayaan-gupta/ridgeline), a real-time
wildfire smoke detection system that watches HPWREN/ALERTWildfire public
lookout cameras and confirms a fire only after three consecutive frames
score above threshold.

This is a genuinely separate service (Next.js web app + FastAPI model
service + Postgres), meant to run alongside InfernoTech via docker-compose,
not to be re-implemented here. InfernoTech talks to it purely through its
documented public REST API (see the repo README's Endpoints table) — no
Ridgeline source was copied or modified.

Used to overlay ground-camera-CONFIRMED detections (higher trust — passed
Ridgeline's 3-consecutive-frame rule) on InfernoTech's map alongside
NASA FIRMS satellite hotspots (broader coverage, lower per-point certainty).
The two are complementary: satellite catches anything, anywhere, with hours
of latency; ground cameras catch what's in view, confirmed within minutes.
"""
import json
import os
import urllib.error
import urllib.request

USER_AGENT = "infernotech-unified-wildfire-platform/1.0"


class RidgelineError(Exception):
    pass


def _base_url():
    url = os.environ.get("RIDGELINE_API_URL")
    if not url:
        raise RidgelineError(
            "No RIDGELINE_API_URL set. Run Ridgeline alongside InfernoTech "
            "(see docker-compose.yml) and set this to its web service URL, "
            "e.g. http://ridgeline-web:3100 in compose or http://localhost:3100 locally."
        )
    return url.rstrip("/")


def fetch_recent_detections(limit=50):
    """GET /api/detections — recent confirmed detections, newest first.
    Returns a list of normalized dicts: {camera_id, camera_name, lat, lon,
    confidence, confirmed_at, verdict}. Raises RidgelineError if
    unconfigured or unreachable, so callers can omit this layer gracefully
    (same fallback pattern as fire_data.py / weather.py / guardian_client.py)."""
    base = _base_url()
    req = urllib.request.Request(
        f"{base}/api/detections?limit={int(limit)}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RidgelineError(f"Ridgeline API error {e.code}: {e.read().decode(errors='replace')[:300]}")
    except urllib.error.URLError as e:
        raise RidgelineError(f"Could not reach Ridgeline at {base}: {e}")
    except json.JSONDecodeError as e:
        raise RidgelineError(f"Ridgeline returned invalid JSON: {e}")

    # Ridgeline's own response shape isn't pinned down without reading its
    # source directly, so this normalizes defensively across the field
    # names its README implies (camera id/name, lat/lng, confidence,
    # timestamp, verdict) and skips anything it can't parse rather than
    # crashing the whole request over one malformed row.
    detections = data.get("detections", data) if isinstance(data, dict) else data
    normalized = []
    for d in detections or []:
        try:
            normalized.append({
                "camera_id": d.get("camera_id") or d.get("cameraId") or d.get("id"),
                "camera_name": d.get("camera_name") or d.get("cameraName") or d.get("name") or "Unknown camera",
                "lat": float(d.get("lat") or d.get("latitude")),
                "lon": float(d.get("lon") or d.get("lng") or d.get("longitude")),
                "confidence": d.get("confidence"),
                "confirmed_at": d.get("confirmed_at") or d.get("confirmedAt") or d.get("timestamp"),
                "verdict": d.get("verdict", "Unanswered"),
            })
        except (TypeError, ValueError):
            continue  # skip malformed rows rather than fail the whole fetch

    return normalized


def fire_test_alert():
    """POST /api/alerts/test — fires a test alert down Ridgeline's real
    alert path. Useful for confirming the two systems are actually wired
    together during a demo."""
    base = _base_url()
    req = urllib.request.Request(
        f"{base}/api/alerts/test",
        data=b"{}",
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RidgelineError(f"Ridgeline API error {e.code}: {e.read().decode(errors='replace')[:300]}")
    except urllib.error.URLError as e:
        raise RidgelineError(f"Could not reach Ridgeline at {base}: {e}")
