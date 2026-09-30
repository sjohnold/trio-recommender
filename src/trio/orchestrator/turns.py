"""Deterministic, explainable candidate scoring."""

from dataclasses import dataclass
from typing import Protocol

from trio.contracts import Role
from trio.orchestrator.alignment import AlignmentPolicy

_ORDER = (Role.PRAGMATIST, Role.LOGICIAN, Role.EMPATH)


class _Stats(Protocol):
    energy: int
    provocation: int


class TurnPersona(Protocol):
    role: Role
    stats: _Stats


@dataclass(frozen=True, slots=True)
class TurnContext:
    last_role: Role | None
    relevance: float
    addressed: bool = False
    cooldown_active: bool = False
    repetition: float = 0.0
    timeout_risk: float = 0.0
    observer: bool = False

    def __post_init__(self) -> None:
        for name in ("relevance", "repetition", "timeout_risk"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be within 0..1")


@dataclass(frozen=True, slots=True)
class TurnScore:
    role: Role
    base: float
    relevance: float
    address: float
    stats: float
    alignment: float
    cooldown: float
    risk: float
    total: float
    should_speak: bool


def _base(last_role: Role | None, candidate: Role) -> float:
    start = 0 if last_role is None else (_ORDER.index(last_role) + 1) % 3
    distance = (_ORDER.index(candidate) - start) % 3
    return (1.0, 0.5, 0.0)[distance]


def score_candidate(
    context: TurnContext,
    persona: TurnPersona,
    policy: AlignmentPolicy,
) -> TurnScore:
    role = Role(persona.role)
    components = {
        "base": _base(context.last_role, role),
        "relevance": context.relevance,
        "address": 1.0 if context.addressed else 0.0,
        "stats": (
            (persona.stats.energy - 5.5) + (persona.stats.provocation - 5.5)
        ) / 9,
        "alignment": policy.order_bias * 0.25,
        "cooldown": -1.0 if context.cooldown_active else 0.0,
        "risk": -(context.repetition + context.timeout_risk),
    }
    total = round(sum(components.values()), 6)
    return TurnScore(
        role,
        **components,
        total=total,
        should_speak=not context.observer or total >= 1.0,
    )
