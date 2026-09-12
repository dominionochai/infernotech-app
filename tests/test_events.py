from infernotech.events import Event, coerce_events


def test_event_mapping_and_sorting():
    events = coerce_events([{"time": 2, "intensity": 3}, {"timestamp": 1, "value": 2}])
    assert events == [Event(1, 2), Event(2, 3)]


def test_sequence_event_defaults():
    event = Event.from_record((1.5,))
    assert event.timestamp == 1.5
    assert event.value == 1.0
