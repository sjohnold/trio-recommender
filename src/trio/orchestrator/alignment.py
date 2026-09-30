"""Deterministic conversational policy for the nine alignment cells."""

from dataclasses import dataclass
from enum import StrEnum

from trio.persona.models import AlignmentPolicyKey


class AllowedMove(StrEnum):
    RESPECT_TURN = "respect_turn"
    RETURN_TO_TASK = "return_to_task"
    STEELMAN = "steelman"
    ENFORCE_FORMAT = "enforce_format"
    REQUEST_EVIDENCE = "request_evidence"
    CHALLENGE_PREMISE = "challenge_weak_premise"
    MEDIATE = "mediate"
    CLARIFY = "clarify"
    DEESCALATE = "deescalate"
    OBSERVE = "observe"
    SKIP_TURN = "skip_turn"
    REFRAME_ARGUMENT = "reframe_argument"
    CREATIVE_PIVOT = "creative_pivot"
    SUPPORT = "support"
    REQUEST_INTERRUPT = "request_interrupt"
    ASSOCIATIVE_SHIFT = "associative_shift"
    VARY_FORMAT = "vary_format"
    CHALLENGE_RELEVANCE = "challenge_relevance"
    ARGUMENT_ATTACK = "argument_attack"


@dataclass(frozen=True, slots=True)
class AlignmentPolicy:
    order_bias: int
    communion_bias: int
    allowed_moves: tuple[AllowedMove, ...]


_POLICIES = {
    "lawful_good": AlignmentPolicy(1, 1, (
        AllowedMove.RESPECT_TURN, AllowedMove.STEELMAN, AllowedMove.RETURN_TO_TASK,
    )),
    "lawful_neutral": AlignmentPolicy(1, 0, (
        AllowedMove.RESPECT_TURN, AllowedMove.ENFORCE_FORMAT,
    )),
    "lawful_evil": AlignmentPolicy(1, -1, (
        AllowedMove.RESPECT_TURN, AllowedMove.CHALLENGE_PREMISE,
        AllowedMove.REQUEST_EVIDENCE,
    )),
    "neutral_good": AlignmentPolicy(0, 1, (
        AllowedMove.MEDIATE, AllowedMove.CLARIFY, AllowedMove.DEESCALATE,
    )),
    "true_neutral": AlignmentPolicy(0, 0, (
        AllowedMove.OBSERVE, AllowedMove.SKIP_TURN,
    )),
    "neutral_evil": AlignmentPolicy(0, -1, (
        AllowedMove.REFRAME_ARGUMENT, AllowedMove.CHALLENGE_PREMISE,
    )),
    "chaotic_good": AlignmentPolicy(-1, 1, (
        AllowedMove.CREATIVE_PIVOT, AllowedMove.SUPPORT,
        AllowedMove.REQUEST_INTERRUPT,
    )),
    "chaotic_neutral": AlignmentPolicy(-1, 0, (
        AllowedMove.ASSOCIATIVE_SHIFT, AllowedMove.VARY_FORMAT,
        AllowedMove.REQUEST_INTERRUPT,
    )),
    "chaotic_evil": AlignmentPolicy(-1, -1, (
        AllowedMove.CHALLENGE_RELEVANCE, AllowedMove.ARGUMENT_ATTACK,
        AllowedMove.REQUEST_INTERRUPT,
    )),
}


def policy_for(alignment: AlignmentPolicyKey | str) -> AlignmentPolicy:
    key = getattr(alignment, "value", alignment)
    try:
        return _POLICIES[key]
    except KeyError as error:
        raise ValueError(f"unsupported alignment: {alignment}") from error
