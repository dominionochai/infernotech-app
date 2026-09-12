"""CPU-only fly-brain flicker detector."""

from .events import Event, coerce_events, load_events
from .features import extract_features
from .classifier import FlickerClassifier, FlickerDetection

__all__ = [
    "Event",
    "coerce_events",
    "load_events",
    "extract_features",
    "FlickerClassifier",
    "FlickerDetection",
]
