"""Sustained rolling personality-drift detection."""
from dataclasses import dataclass
from typing import Mapping

from trio.metrics.features import FeatureVector


@dataclass(frozen=True, slots=True)
class DriftTarget:
    values: Mapping[str, float]
    weights: Mapping[str, float]
    groups: Mapping[str, str]
    threshold: float
    minimum_words: int = 5


@dataclass(frozen=True, slots=True)
class TurnDistance:
    distance: float
    groups: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class DriftState:
    history: tuple[TurnDistance, ...] = ()
    consecutive_windows: int = 0
    terminal_state: str = "COMPLETED"


@dataclass(frozen=True, slots=True)
class DriftObservation:
    state: DriftState
    distance: float | None
    window_distance: float | None
    deviated_groups: tuple[str, ...]
    excluded: str | None
    drift: bool


def _feature(vector: FeatureVector, name: str) -> float:
    if name.startswith("lexicon."):
        return float(vector.lexicon_rates[name.removeprefix("lexicon.")])
    return float(getattr(vector, name))


def update_personality_drift(
    state: DriftState, vector: FeatureVector, target: DriftTarget
) -> DriftObservation:
    excluded = None
    if state.terminal_state != "COMPLETED":
        excluded = state.terminal_state.lower()
    elif vector.word_count < target.minimum_words:
        excluded = "too_short"
    if excluded:
        next_state = DriftState(state.history, state.consecutive_windows)
        return DriftObservation(next_state, None, None, (), excluded, False)
    if set(target.values) != set(target.weights) or set(target.values) != set(target.groups):
        raise ValueError("target values, weights, and groups must have equal keys")
    if any(weight <= 0 for weight in target.weights.values()):
        raise ValueError("feature weights must be positive")
    differences = {
        name: abs(_feature(vector, name) - expected)
        for name, expected in target.values.items()
    }
    total_weight = sum(target.weights.values())
    distance = sum(
        differences[name] * target.weights[name] for name in differences
    ) / total_weight
    group_values: dict[str, list[float]] = {}
    for name, difference in differences.items():
        group_values.setdefault(target.groups[name], []).append(difference)
    group_distance = {
        group: sum(values) / len(values) for group, values in group_values.items()
    }
    history = (*state.history[-4:], TurnDistance(distance, group_distance))
    window_distance = None
    deviated = ()
    qualifies = False
    if len(history) == 5:
        window_distance = sum(item.distance for item in history) / 5
        deviated = tuple(sorted(
            group for group in group_values
            if sum(item.groups.get(group, 0) > target.threshold for item in history) >= 3
        ))
        qualifies = window_distance > target.threshold and len(deviated) >= 3
    consecutive = state.consecutive_windows + 1 if qualifies else 0
    next_state = DriftState(history, consecutive)
    return DriftObservation(
        next_state, distance, window_distance, deviated, None, consecutive >= 2
    )
