"""Versioned weighted distance for Stage 3 voice examples."""

from typing import Protocol

from trio.contracts import Role
from trio.language.contracts import LanguageLock
from trio.persona.models import AlignmentPolicyKey, PersonaStats
from trio.persona.voice_query import VoiceQuery

DISTANCE_VERSION = "1.0.0"
STAT_WEIGHTS = {
    "energy": 0.12,
    "openness": 0.15,
    "nerve": 0.12,
    "sharpness": 0.15,
    "reasoning": 0.16,
    "provocation": 0.15,
    "attunement": 0.15,
}
ALIGNMENT_PENALTY = 0.25
if abs(sum(STAT_WEIGHTS.values()) - 1.0) > 1e-12:
    raise ValueError("voice distance weights must sum to one")


class ScoredVoiceExample(Protocol):
    language: LanguageLock
    role: Role
    stats: PersonaStats
    alignment: AlignmentPolicyKey


class HardFilterMismatch(ValueError):
    pass


def score_example(query: VoiceQuery, example: ScoredVoiceExample) -> float:
    if not query.matches_hard_filters(example.language, example.role):
        raise HardFilterMismatch("voice example language or role does not match")
    stat_distance = sum(
        weight * abs(getattr(query.stats, name) - getattr(example.stats, name)) / 9
        for name, weight in STAT_WEIGHTS.items()
    )
    alignment = 0.0 if query.alignment is example.alignment else ALIGNMENT_PENALTY
    return round(stat_distance + alignment, 6)

