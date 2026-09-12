"""Pseudo-event generation from video frame differences."""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PseudoEvents:
    """Positive and negative thresholded frame-difference events."""

    positive: np.ndarray
    negative: np.ndarray
    delta: np.ndarray


class PseudoEventGenerator:
    """Generate polarity-separated pseudo-events from successive video frames."""

    def __init__(self, threshold: float = 0.08) -> None:
        self.threshold = float(threshold)
        self.previous_frame: np.ndarray | None = None

    @staticmethod
    def _grayscale_float32(frame: np.ndarray) -> np.ndarray:
        array = np.asarray(frame)
        if array.ndim == 3:
            gray = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        elif array.ndim == 2:
            gray = array
        else:
            raise ValueError("frame must be a 2-D grayscale or 3-D BGR image")
        gray = gray.astype(np.float32, copy=False)
        if gray.size and float(np.nanmax(gray)) > 1.0:
            gray = gray / 255.0
        return gray

    def process(self, frame: np.ndarray) -> PseudoEvents:
        """Return events for *frame* and retain it for the next comparison."""
        current = self._grayscale_float32(frame)
        if self.previous_frame is None:
            delta = np.zeros_like(current, dtype=np.float32)
        else:
            if self.previous_frame.shape != current.shape:
                raise ValueError("successive frames must have the same shape")
            delta = current - self.previous_frame
        self.previous_frame = current.copy()
        positive = delta >= self.threshold
        negative = delta <= -self.threshold
        return PseudoEvents(positive=positive, negative=negative, delta=delta)

    def __call__(self, frame: np.ndarray) -> PseudoEvents:
        return self.process(frame)
