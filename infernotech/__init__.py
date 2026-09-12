"""CPU-only fly-brain flicker detector."""

from .events import Event, coerce_events, load_events
from .features import extract_features
from .classifier import FlickerClassifier, FlickerDetection
from .video_events import PseudoEventGenerator, PseudoEvents
from .video_features import extract_region_features
from .video_classifier import RuleClassifier, TwoStateHMM

__all__ = [
    "Event",
    "coerce_events",
    "load_events",
    "extract_features",
    "FlickerClassifier",
    "FlickerDetection",
    "PseudoEventGenerator",
    "PseudoEvents",
    "extract_region_features",
    "RuleClassifier",
    "TwoStateHMM",
]
