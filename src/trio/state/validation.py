"""Dialogue-state validation and an unknown-safe deterministic fallback."""
import json
from dataclasses import dataclass
from typing import Any, Iterable
from trio.state.client import RawStateResult
_PARTIES = {"user", "pragmatist", "logician", "empath"}
_STANCES = {"agree", "disagree", "mixed", "neutral", "unknown"}
_NEXT = _PARTIES | {"none", "unknown"}
class StateValidationError(ValueError):
    pass
@dataclass(frozen=True, slots=True)
class DialogueState:
    tension: float | str
    trend: str
    relations: tuple[dict[str, Any], ...]
    topic_shift: dict[str, Any]
    user_signal: dict[str, Any]
    suggested_next: str
    source: str
    confidence: float
def _number(value: object, low: float, high: float, unknown=False) -> bool:
    return (
        unknown and value == "unknown"
        or isinstance(value, (int, float)) and not isinstance(value, bool)
        and low <= value <= high
    )
def validate_state(raw: RawStateResult | str) -> DialogueState:
    text = raw.raw_json if isinstance(raw, RawStateResult) else raw
    try:
        value = json.loads(text)
        required = {
            "tension", "trend", "relations", "topic_shift",
            "user_signal", "suggested_next",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise ValueError("state fields do not match schema")
        if not _number(value["tension"], 0, 1, True):
            raise ValueError("invalid tension")
        if value["trend"] not in {"rising", "stable", "falling", "unknown"}:
            raise ValueError("invalid trend")
        relations = value["relations"]
        if (not isinstance(relations, list) or len(relations) > 12
                or len({json.dumps(item, sort_keys=True) for item in relations}) != len(relations)):
            raise ValueError("invalid relations")
        confidences = []
        for relation in relations:
            if not isinstance(relation, dict) or set(relation) != {
                "source", "target", "affinity", "confidence",
            }:
                raise ValueError("invalid relation fields")
            if relation["source"] not in _PARTIES or relation["target"] not in _PARTIES:
                raise ValueError("invalid relation party")
            if not _number(relation["affinity"], -1, 1, True):
                raise ValueError("invalid affinity")
            if not _number(relation["confidence"], 0, 1):
                raise ValueError("invalid relation confidence")
            confidences.append(relation["confidence"])
        shift, signal = value["topic_shift"], value["user_signal"]
        if not isinstance(shift, dict) or set(shift) != {"detected", "confidence"}:
            raise ValueError("invalid topic_shift fields")
        if not (isinstance(shift["detected"], bool) or shift["detected"] == "unknown") or not _number(shift["confidence"], 0, 1):
            raise ValueError("invalid topic_shift")
        if not isinstance(signal, dict) or set(signal) != {
            "valence", "arousal", "stance", "confidence",
        }:
            raise ValueError("invalid user_signal fields")
        if not _number(signal["valence"], -1, 1, True) or not _number(signal["arousal"], 0, 1, True):
            raise ValueError("invalid user signal score")
        if signal["stance"] not in _STANCES or not _number(signal["confidence"], 0, 1):
            raise ValueError("invalid user signal")
        if value["suggested_next"] not in _NEXT:
            raise ValueError("invalid suggested_next")
        confidence = min(confidences + [shift["confidence"], signal["confidence"]])
        return DialogueState(
            value["tension"], value["trend"], tuple(relations), shift, signal,
            value["suggested_next"], "model", confidence,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise StateValidationError(str(error)) from error
def fallback_state(
    events: Iterable[object], previous: DialogueState | None
) -> DialogueState:
    latest = list(events)[-1:] or [{}]
    event = latest[0] if isinstance(latest[0], dict) else {}
    shift = event.get("topic_shift", "unknown")
    shift = shift if isinstance(shift, bool) else "unknown"
    user = event if event.get("speaker") == "user" else {}
    stance = user.get("stance", "unknown")
    stance = stance if stance in _STANCES else "unknown"
    tension = previous.tension if previous is not None else "unknown"
    relations = previous.relations if previous is not None else ()
    return DialogueState(
        tension, "unknown", relations,
        {"detected": shift, "confidence": 0.4 if shift != "unknown" else 0.0},
        {"valence": "unknown", "arousal": "unknown", "stance": stance,
         "confidence": 0.4 if stance != "unknown" else 0.0},
        "unknown", "fallback", min(previous.confidence, 0.4) if previous else 0.0,
    )
