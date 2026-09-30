"""Rule-based observations of order and communion behavior."""
from dataclasses import dataclass
from typing import Iterable

from trio.metrics.features import FeatureVector


@dataclass(frozen=True, slots=True)
class WorldviewObservation:
    observed_order: float
    observed_communion: float
    confidence: float
    evidence: tuple[str, ...]
    argument_attack: bool
    personal_attack: bool


def _get(value: object, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _kind(event: object) -> str:
    value = _get(event, "kind", _get(event, "move", event))
    return str(getattr(value, "value", value)).lower()


def observe_worldview(
    utterance: object, events: Iterable[object], features: FeatureVector
) -> WorldviewObservation:
    utterance_id = _get(utterance, "utterance_id", _get(utterance, "id"))
    order_values: list[float] = []
    communion_values: list[float] = []
    evidence: list[str] = []
    argument_attack = personal_attack = False
    for event in events:
        event_utterance = _get(event, "utterance_id")
        if event_utterance and utterance_id and event_utterance != utterance_id:
            continue
        kind = _kind(event)
        if kind in {"queue", "respect_turn", "request_interrupt"}:
            respected = _get(event, "respected", kind == "respect_turn")
            order_values.append(1.0 if respected else -1.0)
            evidence.append("queue")
        elif kind in {"relevance", "return_to_task", "challenge_relevance"}:
            value = _get(event, "value", 1 if kind == "return_to_task" else -1)
            order_values.append(max(-1.0, min(1.0, float(value))))
            evidence.append("relevance")
        elif kind in {"format", "enforce_format"}:
            order_values.append(1.0 if _get(event, "respected", True) else -1.0)
            evidence.append("format")
        elif kind in {"support", "mediate", "steelman", "deescalate"}:
            communion_values.append(1.0)
            evidence.append("support")
        elif kind == "argument_attack":
            communion_values.append(-1.0)
            argument_attack = True
            evidence.append("argument_attack")
        elif kind == "personal_attack":
            communion_values.append(-1.0)
            personal_attack = True
            evidence.append("personal_attack")
    target = _get(utterance, "target")
    if target:
        evidence.append("target")
    affiliation = features.lexicon_rates.get("affiliation", 0)
    if affiliation:
        communion_values.append(min(1.0, affiliation / 10))
        evidence.append("affiliation")
    references = features.reference_rate
    if references:
        communion_values.append(min(1.0, references / 10))
        evidence.append("reference")
    order = sum(order_values) / len(order_values) if order_values else 0.0
    communion = (
        sum(communion_values) / len(communion_values)
        if communion_values else 0.0
    )
    confidence = min(0.95, 0.25 + 0.15 * len(set(evidence)))
    return WorldviewObservation(
        order, communion, confidence, tuple(evidence),
        argument_attack, personal_attack,
    )
