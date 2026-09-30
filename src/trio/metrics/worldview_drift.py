"""Sustained drift of the operational two-axis worldview grid."""
from dataclasses import dataclass
from typing import Sequence

from trio.metrics.worldview import WorldviewObservation

_ORDER = {-1: "chaotic", 0: "neutral", 1: "lawful"}
_COMMUNION = {-1: "evil", 0: "neutral", 1: "good"}
_CELLS = {
    f"{order}_{communion}"
    for order in _ORDER.values() for communion in _COMMUNION.values()
}
_CELLS.remove("neutral_neutral")
_CELLS.add("true_neutral")


def _axis(value: float) -> int:
    return -1 if value < -0.33 else 1 if value > 0.33 else 0


def _cell(order: int, communion: int) -> str:
    if order == communion == 0:
        return "true_neutral"
    return f"{_ORDER[order]}_{_COMMUNION[communion]}"


@dataclass(frozen=True, slots=True)
class WorldviewDriftObservation:
    observed_order: float | None
    observed_communion: float | None
    order_band: int | None
    communion_band: int | None
    observed_cell: str | None
    previous_cell: str | None
    confidence: float
    drift: bool
    excluded: bool


def update_worldview_drift(
    history: Sequence[WorldviewObservation], target_cell: str
) -> WorldviewDriftObservation:
    if target_cell not in _CELLS:
        raise ValueError(f"unsupported target cell: {target_cell}")
    if not history or history[-1].confidence < 0.65:
        confidence = history[-1].confidence if history else 0.0
        return WorldviewDriftObservation(
            None, None, None, None, None, None, confidence, False, True
        )
    eligible = [item for item in history if item.confidence >= 0.65]
    if len(eligible) < 5:
        return WorldviewDriftObservation(
            None, None, None, None, None, None,
            min(item.confidence for item in eligible), False, False,
        )

    def summarize(window):
        order = sum(item.observed_order for item in window) / 5
        communion = sum(item.observed_communion for item in window) / 5
        order_band, communion_band = _axis(order), _axis(communion)
        confidence = min(item.confidence for item in window)
        return order, communion, order_band, communion_band, (
            _cell(order_band, communion_band)
        ), confidence

    current = summarize(eligible[-5:])
    previous = summarize(eligible[-6:-1]) if len(eligible) >= 6 else None
    drift = bool(
        previous and current[4] != target_cell and previous[4] != target_cell
    )
    return WorldviewDriftObservation(
        *current[:5], previous[4] if previous else None, current[5], drift, False
    )
