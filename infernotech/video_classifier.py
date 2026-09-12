"""Rule-based and two-state HMM video-region classifiers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import joblib
import numpy as np
from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler


class RuleClassifier:
    """Classify video regions using the fly-visual weighted rule."""

    @staticmethod
    def clip01(value: float) -> float:
        """Clamp a numeric value to the inclusive [0, 1] interval."""
        return float(np.clip(float(value), 0.0, 1.0))

    def rate_score(self, value: Any) -> float:
        return self.clip01(value)

    def wavelet_score(self, value: Any) -> float:
        return self.clip01(value)

    def zcr_score(self, value: Any) -> float:
        return self.clip01(value)

    def persistence_score(self, value: Any) -> float:
        return self.clip01(value)

    def compute_score(
        self,
        rate: float,
        d1: float,
        d2: float,
        zcr: float,
        persistence: float,
        event_count: int = 0,
    ) -> float:
        """Return the weighted score for one region or feature window."""
        score = (
            0.30 * self.rate_score(rate)
            + 0.30 * self.wavelet_score(float(d1) + float(d2))
            + 0.25 * self.zcr_score(zcr)
            + 0.15 * self.persistence_score(persistence)
        )
        if int(event_count) < 10:
            score *= 0.25
        return self.clip01(score)

    # A short alias is useful to callers that treat the rule as a scorer.
    score = compute_score

    @staticmethod
    def _value(features: Mapping[str, Any], *names: str, default: float = 0.0) -> float:
        for name in names:
            if name in features and features[name] is not None:
                return float(features[name])
        return float(default)

    def _score_region(self, region: Mapping[str, Any]) -> float:
        event_count = int(
            self._value(region, "event_count", "events", "count", default=0)
        )
        rate = self._value(region, "rate_score", "rate", "event_rate")
        d1 = self._value(region, "d1", "wavelet_d1", "detail1")
        d2 = self._value(region, "d2", "wavelet_d2", "detail2")
        zcr = self._value(region, "zcr_score", "zcr", "zero_crossing_rate")
        persistence = self._value(
            region, "persistence_score", "persistence", "temporal_persistence"
        )
        return self.compute_score(rate, d1, d2, zcr, persistence, event_count)

    def predict_regions(
        self,
        regions: Mapping[str, Any] | Iterable[Mapping[str, Any]] | None = None,
        event_count: int | None = None,
        **features: Any,
    ) -> dict[str, Any]:
        """Score one or more regions and return the flame/background decision.

        A region is a mapping with rate, d1, d2, zcr, persistence, and optionally
        event_count fields.  A mapping containing ``regions`` is also accepted.
        """
        if regions is None:
            regions = features
        elif isinstance(regions, Mapping) and "regions" in regions:
            if event_count is None:
                event_count = int(regions.get("event_count", 0))
            regions = regions["regions"]

        if isinstance(regions, Mapping):
            region_list = [regions]
        else:
            region_list = list(regions)

        if not region_list:
            region_scores: list[float] = []
            score = 0.0
        else:
            region_scores = [self._score_region(region) for region in region_list]
            score = float(np.mean(region_scores))

        if event_count is not None and int(event_count) < 10:
            # Apply the low-event penalty once to an aggregate whose component
            # scores were supplied without an event count.
            if any("event_count" not in region for region in region_list):
                score *= 0.25
        score = self.clip01(score)
        return {
            "score": score,
            "label": "flame" if score >= 0.55 else "background",
            "region_scores": region_scores,
        }


class TwoStateHMM:
    """Standardized two-state Gaussian HMM with a stable flame-state mapping."""

    def __init__(self, random_state: int | None = 42, n_iter: int = 100, **kwargs: Any):
        self.scaler = StandardScaler()
        self.model = GaussianHMM(
            n_components=2,
            covariance_type="diag",
            random_state=random_state,
            n_iter=n_iter,
            **kwargs,
        )
        self.flame_state_: int | None = None

    @staticmethod
    def _is_flame(label: Any) -> bool:
        if isinstance(label, str):
            return label.strip().lower() in {"flame", "fire", "1", "true", "yes"}
        return bool(label)

    def fit(self, X: Any, labels: Sequence[Any] | None = None) -> "TwoStateHMM":
        values = np.asarray(X, dtype=float)
        if values.ndim == 1:
            values = values.reshape(-1, 1)
        scaled = self.scaler.fit_transform(values)
        self.model.fit(scaled)
        states = self.model.predict(scaled)

        if labels is not None:
            label_values = list(labels)
            if len(label_values) != len(states):
                raise ValueError("labels must have the same number of rows as X")
            flame_votes = [
                sum(
                    self._is_flame(label_values[index])
                    for index, state in enumerate(states)
                    if state == candidate
                )
                for candidate in range(2)
            ]
            self.flame_state_ = int(np.argmax(flame_votes))
        else:
            # Without labels, use the state with the larger mean in the first
            # standardized feature as a deterministic fallback.
            self.flame_state_ = int(np.argmax(self.model.means_[:, 0]))
        return self

    def _require_fitted(self) -> None:
        if self.flame_state_ is None:
            raise RuntimeError("TwoStateHMM must be fitted before prediction")

    def predict_states(self, X: Any) -> np.ndarray:
        self._require_fitted()
        values = np.asarray(X, dtype=float)
        if values.ndim == 1:
            values = values.reshape(-1, 1)
        return self.model.predict(self.scaler.transform(values))

    def predict(self, X: Any) -> np.ndarray:
        """Return ``flame``/``background`` labels for feature rows."""
        states = self.predict_states(X)
        return np.where(states == self.flame_state_, "flame", "background")

    def save(self, path: str | Path) -> None:
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str | Path) -> "TwoStateHMM":
        loaded = joblib.load(path)
        if not isinstance(loaded, cls):
            raise TypeError(f"expected {cls.__name__}, got {type(loaded).__name__}")
        return loaded
