# Fly-brain flicker detector

This is a small, CPU-only Python 3.10+ scaffold for detecting periodic flicker
in timestamped fly-brain/photodiode events. It is deliberately dependency-light:
the feature extractor and baseline classifier use only the Python standard
library. PyYAML is optional (the CLI has a scalar-YAML fallback).

## Input

JSON, JSONL, and CSV are supported. Each event has `timestamp` and may have
`value` (or `intensity`/`amplitude`) and `channel`. Example JSONL:

```json
{"timestamp": 0.00, "value": 0.1}
{"timestamp": 0.05, "value": 0.9}
```

## Run

```bash
python -m pip install -r requirements.txt
python main.py events.jsonl --config config.yaml
pytest -q
```

The JSON result contains `label` (`flicker` or `no_flicker`), a bounded
`probability`, the raw score, and the complete feature dictionary. The result
is a screening signal, not a biological diagnosis; calibrate the threshold and
validate against labelled recordings before using it in an experiment.

## Python API

```python
from infernotech.classifier import FlickerClassifier
from infernotech.events import Event

result = FlickerClassifier().detect([
    Event(0.0, 0.0), Event(0.05, 1.0), Event(0.10, 0.0), Event(0.15, 1.0)
])
print(result.as_dict())
```

`FlickerClassifier.fit` accepts `(feature_dict, label)` pairs for a small rate
calibration. `save`/`load` use JSON in `models/`; no pickle or GPU runtime is
required.
