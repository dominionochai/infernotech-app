"""Event input and validation helpers for the flicker detector.

The detector deliberately accepts small, dependency-free records so it can be
fed from a photodiode, a microscope export, or a JSON/JSONL fixture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class Event:
    """One time-stamped observation.

    ``value`` is normally luminance or spike amplitude.  A value of 1.0 is a
    useful default for timestamp-only spike/event trains.
    """

    timestamp: float
    value: float = 1.0
    channel: str = "default"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        timestamp = float(self.timestamp)
        value = float(self.value)
        if not math.isfinite(timestamp):
            raise ValueError("event timestamp must be finite")
        if not math.isfinite(value):
            raise ValueError("event value must be finite")
        if not isinstance(self.channel, str) or not self.channel:
            raise ValueError("event channel must be a non-empty string")
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "value", value)

    @classmethod
    def from_record(cls, record: Any) -> "Event":
        if isinstance(record, cls):
            return record
        if isinstance(record, Mapping):
            timestamp = record.get("timestamp", record.get("time", record.get("t")))
            if timestamp is None:
                raise ValueError("event record needs timestamp, time, or t")
            value = record.get("value", record.get("intensity", record.get("amplitude", 1.0)))
            channel = record.get("channel", "default")
            metadata = {k: v for k, v in record.items() if k not in {"timestamp", "time", "t", "value", "intensity", "amplitude", "channel"}}
            return cls(timestamp, value, channel, metadata)
        if isinstance(record, Sequence) and not isinstance(record, (str, bytes)):
            if len(record) == 0:
                raise ValueError("event sequence cannot be empty")
            return cls(record[0], record[1] if len(record) > 1 else 1.0, record[2] if len(record) > 2 else "default")
        raise TypeError(f"unsupported event record: {type(record).__name__}")

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"timestamp": self.timestamp, "value": self.value, "channel": self.channel}
        result.update(dict(self.metadata))
        return result


def coerce_events(records: Iterable[Any], *, sort: bool = True) -> list[Event]:
    """Convert records to events, optionally sorting by timestamp."""
    events = [Event.from_record(record) for record in records]
    if sort:
        events.sort(key=lambda event: event.timestamp)
    return events


def iter_events(path: str | Path) -> Iterator[Event]:
    """Yield events from JSON, JSONL, or CSV based on the file suffix/content."""
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        with source.open(newline="", encoding="utf-8") as handle:
            yield from (Event.from_record(row) for row in csv.DictReader(handle))
        return
    with source.open(encoding="utf-8") as handle:
        if suffix in {".jsonl", ".ndjson"}:
            for line in handle:
                if line.strip():
                    yield Event.from_record(json.loads(line))
            return
        payload = json.load(handle)
    if isinstance(payload, Mapping):
        payload = payload.get("events", [payload])
    if not isinstance(payload, list):
        raise ValueError("JSON input must be an event list or an object with an events list")
    yield from (Event.from_record(record) for record in payload)


def load_events(path: str | Path) -> list[Event]:
    """Load and time-order an event file."""
    return coerce_events(iter_events(path))
