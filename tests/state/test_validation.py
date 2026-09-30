import json
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trio.state.validation import (
    StateValidationError,
    fallback_state,
    validate_state,
)
VALID = {
    "tension": 0.6,
    "trend": "rising",
    "relations": [
        {"source": "user", "target": "empath", "affinity": "unknown", "confidence": 0.7}
    ],
    "topic_shift": {"detected": False, "confidence": 0.8},
    "user_signal": {
        "valence": -0.2, "arousal": "unknown",
        "stance": "disagree", "confidence": 0.6,
    },
    "suggested_next": "empath",
}
def test_valid_state_is_typed_and_bounded() -> None:
    state = validate_state(json.dumps(VALID))
    assert state.source == "model"
    assert state.confidence == 0.6
    assert state.relations[0]["affinity"] == "unknown"
@pytest.mark.parametrize("raw", ["not-json", "{}", json.dumps(dict(VALID, profile={}))])
def test_invalid_json_or_extra_profile_is_explicit(raw: str) -> None:
    with pytest.raises(StateValidationError):
        validate_state(raw)
def test_invalid_state_can_fall_back_without_stopping_session() -> None:
    previous = validate_state(json.dumps(VALID))
    first = fallback_state(
        [{"speaker": "user", "stance": "agree", "topic_shift": True}], previous
    )
    second = fallback_state(
        [{"speaker": "user", "stance": "agree", "topic_shift": True}], previous
    )
    assert first == second
    assert first.source == "fallback" and first.confidence <= 0.4
    assert first.user_signal["stance"] == "agree"
    assert first.user_signal["valence"] == first.user_signal["arousal"] == "unknown"
