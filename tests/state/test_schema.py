import copy
import json
from pathlib import Path

import pytest

SCHEMA = json.loads(
    (Path(__file__).parents[2] / "schemas/dialogue_state.schema.json").read_text()
)
STATE = {
    "tension": 0.4,
    "trend": "stable",
    "relations": [
        {"source": "user", "target": "logician", "affinity": 0.2, "confidence": 0.7}
    ],
    "topic_shift": {"detected": False, "confidence": 0.8},
    "user_signal": {
        "valence": "unknown", "arousal": 0.3,
        "stance": "neutral", "confidence": 0.6,
    },
    "suggested_next": "empath",
}


def validate(value: dict) -> None:
    assert set(value) == set(SCHEMA["required"])
    assert value["tension"] == "unknown" or 0 <= value["tension"] <= 1
    assert value["trend"] in {"rising", "stable", "falling", "unknown"}
    assert len(value["relations"]) <= 12
    for relation in value["relations"]:
        assert set(relation) == {"source", "target", "affinity", "confidence"}
        assert relation["affinity"] == "unknown" or -1 <= relation["affinity"] <= 1
        assert 0 <= relation["confidence"] <= 1
    assert set(value["topic_shift"]) == {"detected", "confidence"}
    assert value["topic_shift"]["detected"] in {True, False, "unknown"}
    signal = value["user_signal"]
    assert set(signal) == {"valence", "arousal", "stance", "confidence"}
    assert signal["valence"] == "unknown" or -1 <= signal["valence"] <= 1
    assert signal["arousal"] == "unknown" or 0 <= signal["arousal"] <= 1
    assert signal["stance"] in {"agree", "disagree", "mixed", "neutral", "unknown"}
    assert 0 <= signal["confidence"] <= 1


def test_bounded_observable_state_is_valid() -> None:
    validate(STATE)
    assert SCHEMA["additionalProperties"] is False


@pytest.mark.parametrize(("path", "value"), [
    (("tension",), 1.1),
    (("user_signal", "diagnosis"), "anxious"),
    (("profile",), {"personality": "fragile"}),
])
def test_unbounded_or_psychological_fields_are_rejected(path, value) -> None:
    state = copy.deepcopy(STATE)
    target = state
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises((AssertionError, TypeError)):
        validate(state)
