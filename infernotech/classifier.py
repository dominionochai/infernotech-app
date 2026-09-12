"""A transparent CPU-only classifier for periodic flicker event windows."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .events import Event
from .features import extract_features


@dataclass(frozen=True, slots=True)
class FlickerDetection:
    label: str
    probability: float
    score: float
    features: dict[str, float]

    @property
    def is_flicker(self) -> bool:
        return self.label == "flicker"

    def as_dict(self) -> dict[str, Any]:
        return {"label": self.label, "probability": self.probability, "score": self.score, "is_flicker": self.is_flicker, "features": self.features}


class FlickerClassifier:
    """Rule-based baseline with optional learned positive/negative centroids.

    The baseline is intentionally explainable and has no GPU or model-runtime
    dependency.  ``fit`` can calibrate it from labelled feature dictionaries,
    while the default remains useful for a first detector scaffold.
    """

    def __init__(self, threshold: float = 0.55, min_frequency_hz: float = 2.0, max_frequency_hz: float = 120.0) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self.threshold = float(threshold)
        self.min_frequency_hz = float(min_frequency_hz)
        self.max_frequency_hz = float(max_frequency_hz)
        self._positive_rate: float | None = None
        self._negative_rate: float | None = None

    def score(self, features: Mapping[str, float]) -> float:
        frequency = float(features.get("dominant_frequency_hz", 0.0))
        periodicity = max(0.0, min(1.0, float(features.get("periodicity", features.get("flicker_score", 0.0)))))
        if self.min_frequency_hz <= frequency <= self.max_frequency_hz:
            band = 1.0
        else:
            band = 0.0
        score = 0.65 * periodicity + 0.35 * band
        if self._positive_rate is not None and self._negative_rate is not None:
            rate = float(features.get("rate_hz", 0.0))
            span = max(abs(self._positive_rate - self._negative_rate), 1e-9)
            score = 0.8 * score + 0.2 * max(0.0, min(1.0, 0.5 + (rate - self._negative_rate) / (2.0 * span)))
        return max(0.0, min(1.0, score))

    def predict_one(self, features: Mapping[str, float]) -> FlickerDetection:
        score = self.score(features)
        label = "flicker" if score >= self.threshold else "no_flicker"
        probability = score if label == "flicker" else 1.0 - score
        return FlickerDetection(label, probability, score, dict(features))

    def detect(self, events: Iterable[Event | Mapping[str, Any] | tuple]) -> FlickerDetection:
        features = extract_features(events, flicker_min_hz=self.min_frequency_hz, flicker_max_hz=self.max_frequency_hz)
        return self.predict_one(features)

    def fit(self, samples: Iterable[tuple[Mapping[str, float], str]]) -> "FlickerClassifier":
        positive, negative = [], []
        for features, label in samples:
            (positive if str(label).lower() in {"flicker", "positive", "1", "true"} else negative).append(float(features.get("rate_hz", 0.0)))
        if not positive or not negative:
            raise ValueError("fit requires at least one flicker and one no_flicker sample")
        self._positive_rate, self._negative_rate = sum(positive) / len(positive), sum(negative) / len(negative)
        return self

    def predict(self, samples: Mapping[str, float] | Iterable[Mapping[str, float]]) -> str | list[str]:
        if isinstance(samples, Mapping):
            return self.predict_one(samples).label
        return [self.predict_one(sample).label for sample in samples]

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({"threshold": self.threshold, "min_frequency_hz": self.min_frequency_hz, "max_frequency_hz": self.max_frequency_hz, "positive_rate": self._positive_rate, "negative_rate": self._negative_rate}, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "FlickerClassifier":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        model = cls(data.get("threshold", 0.55), data.get("min_frequency_hz", 2.0), data.get("max_frequency_hz", 120.0))
        model._positive_rate, model._negative_rate = data.get("positive_rate"), data.get("negative_rate")
        return model


Detector = FlickerClassifier
