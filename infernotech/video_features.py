"""Spatial and temporal features for polarity-separated video events."""

from __future__ import annotations

from typing import Any, Iterable, List, Sequence, Tuple

import numpy as np
import pywt


FEATURE_NAMES = [
    "event_count",
    "polarity_balance",
    "event_rate_mean",
    "event_rate_variance",
    "wavelet_d1_energy",
    "wavelet_d2_energy",
    "wavelet_d3_energy",
    "wavelet_zero_crossing_rate",
    "spatial_concentration",
    "short_term_persistence",
]


def zero_crossing_rate(values: Iterable[float]) -> float:
    """Return the fraction of adjacent samples that cross zero.

    Zero-valued samples are ignored when determining the sign.  This makes a
    run of zeros between two samples behave as a single transition rather than
    introducing an arbitrary number of crossings.
    """

    array = np.asarray(list(values) if not isinstance(values, np.ndarray) else values)
    array = np.asarray(array, dtype=np.float64).reshape(-1)
    array = array[np.isfinite(array)]
    if array.size < 2:
        return 0.0
    signs = np.sign(array)
    signs = signs[signs != 0]
    if signs.size < 2:
        return 0.0
    return float(np.count_nonzero(signs[1:] != signs[:-1]) / (signs.size - 1))


def region_slices(rows: int = 2, cols: int = 2) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Return normalized ``((row_start, row_end), (col_start, col_end))`` regions."""

    rows = int(rows)
    cols = int(cols)
    if rows <= 0 or cols <= 0:
        raise ValueError("rows and cols must be positive")
    return [
        ((row / rows, (row + 1) / rows), (col / cols, (col + 1) / cols))
        for row in range(rows)
        for col in range(cols)
    ]


def _safe_wavelet_features(
    values: Sequence[float], wavelet: str = "db2", level: int = 3
) -> Tuple[float, float, float, float]:
    """Compute stable detail-band energies and a wavelet zero-crossing rate."""

    level = int(level)
    if level < 1:
        raise ValueError("wavelet_level must be at least 1")

    target_length = 2 ** (level + 2)
    signal = np.asarray(values, dtype=np.float64).reshape(-1)
    signal = np.nan_to_num(signal, nan=0.0, posinf=0.0, neginf=0.0)
    if signal.size == 0:
        signal = np.zeros(target_length, dtype=np.float64)
    elif signal.size < target_length:
        signal = np.pad(signal, (0, target_length - signal.size), mode="edge")

    coefficients = pywt.wavedec(
        signal, wavelet=wavelet, level=level, mode="periodization"
    )
    # wavedec returns [cA_level, cD_level, ..., cD1].  The requested
    # d1/d2/d3 ordering is therefore the reverse of the detail list.
    details = coefficients[1:]
    detail_by_level = {level - index: detail for index, detail in enumerate(details)}
    energies = [
        float(np.sum(np.square(detail_by_level.get(index, np.zeros(0)))))
        for index in (1, 2, 3)
    ]
    detail_signal = np.concatenate(details) if details else np.zeros(0)
    return (*energies, zero_crossing_rate(detail_signal))


def _region_index(y: float, x: float, height: float, width: float, rows: int, cols: int) -> int:
    """Map a spatial coordinate to a row-major region index."""

    if 0.0 <= y <= 1.0 and 0.0 <= x <= 1.0 and height <= 1.0 and width <= 1.0:
        normalized_y, normalized_x = y, x
    else:
        normalized_y = y / max(height, 1.0)
        normalized_x = x / max(width, 1.0)
    region_row = min(rows - 1, max(0, int(normalized_y * rows)))
    region_col = min(cols - 1, max(0, int(normalized_x * cols)))
    return region_row * cols + region_col


def _as_event_rows(history: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract time, y and x columns from common event-history formats."""

    if history is None:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    if isinstance(history, np.ndarray):
        array = history
    else:
        try:
            array = np.asarray(history)
        except (TypeError, ValueError):
            array = np.zeros(0)

    if array.size == 0:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    if array.ndim == 1:
        # A one-dimensional history has time order but no spatial metadata.
        return np.arange(array.size, dtype=np.float64), np.zeros(array.size), np.zeros(array.size)
    if array.ndim != 2:
        return np.zeros(0), np.zeros(0), np.zeros(0)

    numeric = np.asarray(array, dtype=np.float64)
    count, columns = numeric.shape
    if columns >= 3:
        # Event rows conventionally use timestamp, x, y.  Accept the common
        # timestamp, y, x ordering too by treating the two spatial columns
        # symmetrically for region assignment.
        return numeric[:, 0], numeric[:, 2], numeric[:, 1]
    if columns == 2:
        # With two columns, use the first as time and the second as a scalar
        # spatial coordinate.  This keeps compact histories useful and stable.
        return numeric[:, 0], numeric[:, 1], np.zeros(count)
    return np.arange(count, dtype=np.float64), np.zeros(count), np.zeros(count)


def _frame_region_counts(history: Any, rows: int, cols: int) -> Tuple[np.ndarray, np.ndarray] | None:
    """Return per-frame regional counts for a stack of spatial frames."""

    try:
        array = np.asarray(history, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    if array.ndim < 3:
        return None
    if array.ndim > 3:
        array = np.sum(np.abs(array), axis=tuple(range(3, array.ndim)))
    frames, height, width = array.shape
    result = np.zeros((frames, rows * cols), dtype=np.float64)
    for region_number, ((row_start, row_end), (col_start, col_end)) in enumerate(
        region_slices(rows, cols)
    ):
        r0, r1 = int(row_start * height), int(row_end * height)
        c0, c1 = int(col_start * width), int(col_end * width)
        r1 = max(r0 + 1, r1)
        c1 = max(c0 + 1, c1)
        result[:, region_number] = np.sum(np.abs(array[:, r0:r1, c0:c1]), axis=(1, 2))
    return result, np.zeros_like(result)


def _event_region_counts(
    positive_history: Any,
    negative_history: Any,
    bin_seconds: float,
    rows: int,
    cols: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Bin event rows into spatial regions."""

    positive = _as_event_rows(positive_history)
    negative = _as_event_rows(negative_history)
    all_times = np.concatenate((positive[0], negative[0]))
    if all_times.size:
        all_times = all_times[np.isfinite(all_times)]
    start = float(np.min(all_times)) if all_times.size else 0.0
    duration = max(float(bin_seconds), np.finfo(float).eps)
    max_time = float(np.max(all_times)) if all_times.size else start
    bins = max(1, int(np.floor((max_time - start) / duration)) + 1)
    pos_counts = np.zeros((bins, rows * cols), dtype=np.float64)
    neg_counts = np.zeros_like(pos_counts)

    all_y = np.concatenate((positive[1], negative[1]))
    all_x = np.concatenate((positive[2], negative[2]))
    finite_y = all_y[np.isfinite(all_y)]
    finite_x = all_x[np.isfinite(all_x)]
    height = float(np.max(finite_y) + 1.0) if finite_y.size else 1.0
    width = float(np.max(finite_x) + 1.0) if finite_x.size else 1.0

    def add_events(event_rows: Tuple[np.ndarray, np.ndarray, np.ndarray], output: np.ndarray) -> None:
        times, ys, xs = event_rows
        for timestamp, y, x in zip(times, ys, xs):
            if not (np.isfinite(timestamp) and np.isfinite(y) and np.isfinite(x)):
                continue
            time_bin = min(bins - 1, max(0, int(np.floor((timestamp - start) / duration))))
            region = _region_index(float(y), float(x), height, width, rows, cols)
            output[time_bin, region] += 1.0

    add_events(positive, pos_counts)
    add_events(negative, neg_counts)
    return pos_counts, neg_counts


def _persistence(values: np.ndarray) -> float:
    if values.size < 2 or not np.any(values):
        return 0.0
    left, right = values[:-1], values[1:]
    if np.std(left) == 0.0 or np.std(right) == 0.0:
        return 1.0 if np.array_equal(left, right) and np.any(left) else 0.0
    return float(np.corrcoef(left, right)[0, 1])


def extract_region_features(
    positive_history: Any,
    negative_history: Any,
    bin_seconds: float,
    rows: int = 2,
    cols: int = 2,
    wavelet: str = "db2",
    wavelet_level: int = 3,
) -> np.ndarray:
    """Return one float32 feature vector per spatial region.

    Histories may be stacks of ``(time, height, width)`` frames or event rows.
    Event rows use ``(timestamp, x, y)`` coordinates; positive and negative
    histories are kept separate so polarity balance remains well-defined.
    """

    rows, cols = int(rows), int(cols)
    if rows <= 0 or cols <= 0:
        raise ValueError("rows and cols must be positive")
    if float(bin_seconds) <= 0:
        raise ValueError("bin_seconds must be positive")

    frame_counts = _frame_region_counts(positive_history, rows, cols)
    negative_frame_counts = _frame_region_counts(negative_history, rows, cols)
    if frame_counts is not None and negative_frame_counts is not None:
        positive_counts, _ = frame_counts
        negative_counts, _ = negative_frame_counts
        length = min(len(positive_counts), len(negative_counts))
        positive_counts = positive_counts[:length]
        negative_counts = negative_counts[:length]
    else:
        positive_counts, negative_counts = _event_region_counts(
            positive_history, negative_history, float(bin_seconds), rows, cols
        )

    number_of_regions = rows * cols
    output = np.zeros((number_of_regions, len(FEATURE_NAMES)), dtype=np.float32)
    total_all_regions = float(np.sum(positive_counts) + np.sum(negative_counts))
    for region in range(number_of_regions):
        positive = positive_counts[:, region]
        negative = negative_counts[:, region]
        rates = (positive + negative) / float(bin_seconds)
        event_count = float(np.sum(positive) + np.sum(negative))
        polarity_balance = (
            float(np.sum(positive) - np.sum(negative)) / event_count
            if event_count
            else 0.0
        )
        d1, d2, d3, wavelet_zcr = _safe_wavelet_features(
            rates, wavelet=wavelet, level=wavelet_level
        )
        output[region] = np.asarray(
            [
                event_count,
                polarity_balance,
                float(np.mean(rates)) if rates.size else 0.0,
                float(np.var(rates)) if rates.size else 0.0,
                d1,
                d2,
                d3,
                wavelet_zcr,
                event_count / total_all_regions if total_all_regions else 0.0,
                _persistence(rates),
            ],
            dtype=np.float32,
        )
    return output
