"""Flask endpoints for the Infernotech fly-brain video detector."""

from __future__ import annotations

import os
import sys
import tempfile
from collections import deque

from flask import Blueprint, jsonify, request

# webapp/ is one level below the repository root, where infernotech/ and config.yaml live.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    import cv2
    import numpy as np
    import yaml

    from infernotech.video_classifier import RuleClassifier
    from infernotech.video_events import PseudoEventGenerator
    from infernotech.video_features import extract_region_features

    _DEPENDENCY_ERROR = None
except Exception as exc:  # pragma: no cover - exercised when optional runtime deps are absent
    cv2 = None
    np = None
    yaml = None
    PseudoEventGenerator = None
    RuleClassifier = None
    extract_region_features = None
    _DEPENDENCY_ERROR = exc


detector_bp = Blueprint("detector", __name__)


def _settings():
    """Load the repository detector configuration, with safe defaults."""
    defaults = {
        "threshold": 0.55,
        "video": {
            "threshold": 0.08,
            "grid_rows": 2,
            "grid_cols": 2,
        },
        "features": {"wavelet": "db2", "wavelet_level": 3},
    }
    path = os.path.join(REPO_ROOT, "config.yaml")
    if yaml is None or not os.path.exists(path):
        return defaults
    with open(path, "r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    video = dict(defaults["video"])
    video.update(loaded.get("video") or {})
    features = dict(defaults["features"])
    features.update(loaded.get("features") or {})
    defaults.update(loaded)
    defaults["video"] = video
    defaults["features"] = features
    return defaults


def _missing_dependencies():
    if _DEPENDENCY_ERROR is None:
        return None
    return "Fly-Brain detector dependencies unavailable: {}".format(_DEPENDENCY_ERROR)


@detector_bp.get("/api/detect/health")
def detector_health():
    return jsonify(
        {
            "status": "ok",
            "module": "infernotech.video",
            "classifier": "rule",
        }
    )


@detector_bp.post("/api/detect")
def detect_video():
    dependency_error = _missing_dependencies()
    if dependency_error:
        return jsonify({"error": dependency_error}), 500

    temp_path = None
    source = None
    upload = request.files.get("video")
    if upload is not None and upload.filename:
        suffix = os.path.splitext(upload.filename)[1] or ".mp4"
        temporary = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temporary.name
        temporary.close()
        upload.save(temp_path)
        source = temp_path
    else:
        payload = request.get_json(silent=True) or {}
        source = payload.get("video_url")

    if not source:
        return jsonify({"error": "Provide a multipart video field or JSON video_url."}), 400

    capture = None
    try:
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            return jsonify({"error": "Video could not be opened."}), 400

        settings = _settings()
        video_settings = settings.get("video", {})
        feature_settings = settings.get("features", {})
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if not np.isfinite(fps) or fps <= 0.0:
            fps = 30.0
        bin_seconds = 1.0 / fps
        rows = int(video_settings.get("grid_rows", video_settings.get("rows", 2)))
        cols = int(video_settings.get("grid_cols", video_settings.get("cols", 2)))
        event_threshold = float(video_settings.get("threshold", 0.08))
        generator = PseudoEventGenerator(threshold=event_threshold)
        classifier = RuleClassifier()
        positive_history = deque(maxlen=16)
        negative_history = deque(maxlen=16)
        frames_processed = 0
        latest = {
            "score": 0.0,
            "decision": "background",
            "region_scores": [0.0] * (rows * cols),
        }

        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frames_processed += 1
            events = generator(frame)
            positive_history.append(np.asarray(events.positive, dtype=np.float32))
            negative_history.append(np.asarray(events.negative, dtype=np.float32))

            # Four one-frame bins are the configured warm-up before classification.
            if frames_processed <= 4:
                continue
            features = extract_region_features(
                positive_history,
                negative_history,
                bin_seconds=bin_seconds,
                rows=rows,
                cols=cols,
                wavelet=str(feature_settings.get("wavelet", "db2")),
                wavelet_level=int(feature_settings.get("wavelet_level", 3)),
            )
            result = classifier.predict_regions(features)
            region_scores = [float(value) for value in result.get("region_scores", [])]
            latest = {
                "score": float(result.get("score", 0.0)),
                "decision": str(result.get("label", "background")),
                "region_scores": region_scores,
            }

        return jsonify(
            {
                "score": float(latest["score"]),
                "decision": "flame" if latest["decision"] == "flame" else "background",
                "region_scores": latest["region_scores"],
                "frames_processed": int(frames_processed),
                "duration_sec": float(frames_processed / fps),
            }
        )
    except Exception as exc:
        return jsonify({"error": "Fly-Brain detector failed: {}".format(exc)}), 500
    finally:
        if capture is not None:
            capture.release()
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
