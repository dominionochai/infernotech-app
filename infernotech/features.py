"""Small, explainable temporal features for fly-brain flicker detection."""

from __future__ import annotations

import math
from statistics import fmean, pstdev
from typing import Any, Iterable, Mapping

from .events import Event, coerce_events


FEATURE_NAMES = (
    "event_count", "duration_s", "rate_hz", "mean_value", "std_value",
    "mean_isi_s", "isi_cv", "burstiness", "dominant_frequency_hz",
    "periodicity", "flicker_score",
)


def _dft_peak(values: list[float], sample_rate: float) -> tuple[float, float]:
    """Return (frequency, normalized power) using a dependency-free DFT."""
    n = len(values)
    if n < 4 or sample_rate <= 0:
        return 0.0, 0.0
    centered = [value - fmean(values) for value in values]
    total_power = sum(value * value for value in centered)
    if total_power <= 1e-15:
        return 0.0, 0.0
    best_frequency, best_power = 0.0, 0.0
    for k in range(1, n // 2 + 1):
        real = sum(value * math.cos(2.0 * math.pi * k * i / n) for i, value in enumerate(centered))
        imag = sum(value * math.sin(2.0 * math.pi * k * i / n) for i, value in enumerate(centered))
        power = (real * real + imag * imag) / (n * total_power)
        if power > best_power:
            best_frequency, best_power = k * sample_rate / n, power
    return best_frequency, min(1.0, max(0.0, best_power))


def extract_features(events: Iterable[Event | Mapping[str, Any] | tuple], *, flicker_min_hz: float = 2.0, flicker_max_hz: float = 120.0) -> dict[str, float]:
    """Extract deterministic temporal and periodicity features.

    No NumPy/SciPy is required.  Empty and single-event windows are valid and
    return zero-valued features, which makes streaming callers straightforward.
    """
    ordered = coerce_events(events)
    count = len(ordered)
    if not count:
        return {name: 0.0 for name in FEATURE_NAMES}
    timestamps = [event.timestamp for event in ordered]
    values = [event.value for event in ordered]
    duration = max(0.0, timestamps[-1] - timestamps[0])
    intervals = [b - a for a, b in zip(timestamps, timestamps[1:]) if b > a]
    mean_isi = fmean(intervals) if intervals else 0.0
    isi_cv = (pstdev(intervals) / mean_isi) if len(intervals) > 1 and mean_isi > 0 else 0.0
    burstiness = ((isi_cv - 1.0) / (isi_cv + 1.0)) if isi_cv >= 0 else 0.0
    rate = (count - 1) / duration if duration > 0 and count > 1 else 0.0
    mean_value = fmean(values)
    std_value = pstdev(values) if count > 1 else 0.0
    # Timestamp-only event trains are represented by impulses at their event times.
    # For sampled values, use the observed value sequence directly.
    if len(values) >= 4 and std_value > 0:
        sample_rate = (count - 1) / duration if duration > 0 else 0.0
        frequency, periodicity = _dft_peak(values, sample_rate)
    else:
        frequency = (1.0 / mean_isi) if mean_isi > 0 else 0.0
        periodicity = max(0.0, 1.0 - min(1.0, isi_cv)) if len(intervals) >= 2 else 0.0
    in_band = flicker_min_hz <= frequency <= flicker_max_hz
    flicker_score = max(0.0, min(1.0, periodicity * (1.0 if in_band else 0.25)))
    return {
        "event_count": float(count), "duration_s": duration, "rate_hz": rate,
        "mean_value": mean_value, "std_value": std_value, "mean_isi_s": mean_isi,
        "isi_cv": isi_cv, "burstiness": burstiness,
        "dominant_frequency_hz": frequency, "periodicity": periodicity,
        "flicker_score": flicker_score,
    }


def feature_vector(features: Mapping[str, float]) -> list[float]:
    """Return features in the stable ``FEATURE_NAMES`` order."""
    return [float(features.get(name, 0.0)) for name in FEATURE_NAMES]


extract_feature_vector = feature_vector
