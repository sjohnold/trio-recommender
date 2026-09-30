"""Textual transition points and bounded AI-interruption decisions."""
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
class TRPReason(StrEnum):
    EMPTY = "empty"
    TERMINAL = "terminal_punctuation"
    HOLD_PUNCTUATION = "hold_punctuation"
    UNCLOSED = "unclosed_delimiter"
    CONNECTOR = "unfinished_connector"
    SHORT = "insufficient_content"
@dataclass(frozen=True, slots=True)
class TRPReport:
    is_trp: bool
    hold: bool
    reason: TRPReason
_CONNECTOR = re.compile(
    r"(?:\bif|\bbecause|\band|\bbut|\bесли|\bпотому\s+что|\bи|\bно|"
    r"\bako|\bjer|\bali)\s*$",
    re.IGNORECASE,
)
_LIST_MARKER = re.compile(r"(?:^|\n)\s*(?:[-*]|\d+[.)])\s*$")
def detect_trp(partial: str) -> TRPReport:
    text = partial.rstrip()
    if not text:
        return TRPReport(False, True, TRPReason.EMPTY)
    if text[-1] in ",:;—–-" or _LIST_MARKER.search(text):
        return TRPReport(False, True, TRPReason.HOLD_PUNCTUATION)
    if any(text.count(left) > text.count(right) for left, right in (
        ("(", ")"), ("[", "]"), ("{", "}"),
    )):
        return TRPReport(False, True, TRPReason.UNCLOSED)
    if _CONNECTOR.search(text):
        return TRPReport(False, True, TRPReason.CONNECTOR)
    if len(text.split()) < 8:
        return TRPReport(False, False, TRPReason.SHORT)
    if text[-1] in ".!?":
        return TRPReport(True, False, TRPReason.TERMINAL)
    return TRPReport(False, False, TRPReason.SHORT)
class InterruptCause(StrEnum):
    ADDRESSED_CALL = "addressed_call"
    FACTUAL_CONTRADICTION = "factual_contradiction"
    TOPIC_SHIFT = "topic_shift"
    SOFT_TIMEOUT = "soft_timeout"
    USER_EVENT_RELEVANCE = "user_event_relevance"
class DecisionReason(StrEnum):
    ALLOWED = "allowed"
    NO_CAUSE = "no_legitimate_reason"
    SHORT_FRAGMENT = "insufficient_fragment"
    COOLDOWN = "cooldown_active"
    LIMIT = "interrupt_limit"
    BELOW_THRESHOLD = "below_threshold"
class _Stats(Protocol):
    energy: int
    provocation: int
class _Candidate(Protocol):
    stats: _Stats
class _Current(Protocol):
    text: str
@dataclass(frozen=True, slots=True)
class InterruptContext:
    causes: frozenset[InterruptCause]
    candidate_score: float
    alignment_order_bias: int
    cooldown_active: bool = False
    interrupts_used: int = 0
    minimum_words: int = 8
@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    reason: DecisionReason
    threshold: float
def may_interrupt(
    candidate: _Candidate,
    current: _Current,
    context: InterruptContext,
) -> Decision:
    threshold = round(
        1.5
        - (candidate.stats.provocation - 5) * 0.1
        - (candidate.stats.energy - 5) * 0.05
        + context.alignment_order_bias * 0.2,
        3,
    )
    reason = DecisionReason.ALLOWED
    if not context.causes:
        reason = DecisionReason.NO_CAUSE
    elif len(current.text.split()) < context.minimum_words:
        reason = DecisionReason.SHORT_FRAGMENT
    elif context.cooldown_active:
        reason = DecisionReason.COOLDOWN
    elif context.interrupts_used >= 1:
        reason = DecisionReason.LIMIT
    elif context.candidate_score < threshold:
        reason = DecisionReason.BELOW_THRESHOLD
    return Decision(reason is DecisionReason.ALLOWED, reason, threshold)
