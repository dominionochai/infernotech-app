from infernotech.classifier import FlickerClassifier
from infernotech.events import Event
from infernotech.features import FEATURE_NAMES, extract_features


def test_empty_window_has_stable_schema():
    features = extract_features([])
    assert set(features) == set(FEATURE_NAMES)
    assert all(value == 0.0 for value in features.values())


def test_regular_alternating_signal_is_periodic():
    events = [Event(i * 0.05, float(i % 2)) for i in range(40)]
    features = extract_features(events)
    assert features["dominant_frequency_hz"] > 0
    assert 0.0 <= features["flicker_score"] <= 1.0
    assert features["periodicity"] > 0


def test_classifier_returns_serializable_detection():
    result = FlickerClassifier().detect([Event(i * 0.05, float(i % 2)) for i in range(40)])
    payload = result.as_dict()
    assert payload["label"] in {"flicker", "no_flicker"}
    assert 0.0 <= payload["probability"] <= 1.0
