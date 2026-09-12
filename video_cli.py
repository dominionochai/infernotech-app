"""Live/video fly-visual pipeline."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from infernotech.video_classifier import RuleClassifier
from infernotech.video_events import PseudoEventGenerator
from infernotech.video_features import extract_region_features


def _load_config(path: str) -> dict[str, Any]:
    """Load scalar YAML settings, with a dependency-free fallback."""
    try:
        import yaml
    except ImportError:
        yaml = None

    if yaml is not None:
        with open(path, encoding="utf-8") as handle:
            values = yaml.safe_load(handle) or {}
        return values if isinstance(values, dict) else {}

    values: dict[str, Any] = {}
    config_path = Path(path)
    if not config_path.exists():
        return values
    for line in config_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        try:
            values[key] = float(value)
        except ValueError:
            values[key] = value.strip("'\"")
    return values


def _source(value: str) -> int | str:
    try:
        return int(value)
    except ValueError:
        return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fly-visual video pipeline")
    parser.add_argument("source", help="video path or camera index")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--no-display", action="store_true")
    args = parser.parse_args(argv)

    settings = _load_config(args.config)
    event_threshold = float(settings.get("event_threshold", 0.08))
    bin_seconds = float(settings.get("bin_seconds", 1.0))
    rows = int(settings.get("rows", 2))
    cols = int(settings.get("cols", 2))
    wavelet = str(settings.get("wavelet", "db2"))
    wavelet_level = int(settings.get("wavelet_level", 3))

    capture = cv2.VideoCapture(_source(args.source))
    if not capture.isOpened():
        return 1

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if not np.isfinite(fps) or fps <= 0.0:
        fps = 30.0

    generator = PseudoEventGenerator(threshold=event_threshold)
    classifier = RuleClassifier()
    positive_history: deque[np.ndarray] = deque(maxlen=16)
    negative_history: deque[np.ndarray] = deque(maxlen=16)

    positive_bin: np.ndarray | None = None
    negative_bin: np.ndarray | None = None
    current_bin = -1
    frame_number = 0
    overlay = ""
    overlay_color = (0, 255, 0)

    def classify_history() -> None:
        nonlocal overlay, overlay_color
        if len(positive_history) < 4:
            return
        features = extract_region_features(
            positive_history,
            negative_history,
            bin_seconds=bin_seconds,
            rows=rows,
            cols=cols,
            wavelet=wavelet,
            wavelet_level=wavelet_level,
        )
        result = classifier.predict_regions(features)
        score = float(result["score"])
        decision = str(result["label"])
        print(f"flicker_score={score:.2f} decision={decision}")
        overlay = f"flicker_score={score:.2f} decision={decision}"
        overlay_color = (0, 255, 0) if decision == "flame" else (0, 0, 255)

    def close_bin() -> None:
        nonlocal positive_bin, negative_bin
        if positive_bin is None or negative_bin is None:
            return
        positive_history.append(positive_bin)
        negative_history.append(negative_bin)
        classify_history()
        positive_bin = None
        negative_bin = None

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame = cv2.resize(frame, (320, 240))
            events = generator(frame)
            bin_number = int((frame_number / fps) // bin_seconds)
            if bin_number != current_bin:
                close_bin()
                current_bin = bin_number
                positive_bin = np.zeros(frame.shape[:2], dtype=np.float32)
                negative_bin = np.zeros(frame.shape[:2], dtype=np.float32)

            positive_bin = np.maximum(positive_bin, events.positive.astype(np.float32))
            negative_bin = np.maximum(negative_bin, events.negative.astype(np.float32))

            if not args.no_display:
                display = frame.copy()
                if overlay:
                    cv2.putText(
                        display,
                        overlay,
                        (8, 24),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.48,
                        overlay_color,
                        1,
                        cv2.LINE_AA,
                    )
                cv2.imshow("fly-visual", display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
            frame_number += 1
    finally:
        close_bin()
        capture.release()
        if not args.no_display:
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
