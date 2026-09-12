"""Command-line entry point for the fly-brain flicker detector."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from infernotech.classifier import FlickerClassifier
from infernotech.events import load_events


def _config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        import yaml  # type: ignore
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return data if isinstance(data, dict) else {}
    except ImportError:
        # Accept the simple scalar YAML used by config.yaml without making the
        # detector depend on a non-standard parser.
        values: dict[str, Any] = {}
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" in line:
                key, value = (part.strip() for part in line.split(":", 1))
                try:
                    values[key] = float(value)
                except ValueError:
                    values[key] = value.strip("'\"")
        return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect periodic fly-brain flicker from an event file")
    parser.add_argument("input", help="JSON, JSONL, or CSV event file")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model", help="optional JSON model saved by FlickerClassifier.save")
    args = parser.parse_args(argv)
    settings = _config(args.config)
    if args.model:
        classifier = FlickerClassifier.load(args.model)
    else:
        classifier = FlickerClassifier(
            threshold=float(settings.get("threshold", 0.55)),
            min_frequency_hz=float(settings.get("min_frequency_hz", 2.0)),
            max_frequency_hz=float(settings.get("max_frequency_hz", 120.0)),
        )
    result = classifier.detect(load_events(args.input))
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
