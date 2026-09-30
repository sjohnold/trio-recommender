import sys
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trio.orchestrator.interruptions import (
    DecisionReason,
    InterruptCause,
    InterruptContext,
    detect_trp,
    may_interrupt,
)
def test_detects_terminal_and_hold_boundaries() -> None:
    assert detect_trp("This complete sentence has enough words to pass the boundary.").is_trp
    for partial in (
        "This clause is clearly unfinished and still waiting,",
        "This clause will continue because",
        "This clause has an open (group of words",
        "1.",
    ):
        report = detect_trp(partial)
        assert not report.is_trp and report.hold
def candidate(energy=5, provocation=5):
    return SimpleNamespace(stats=SimpleNamespace(
        energy=energy, provocation=provocation
    ))
CURRENT = SimpleNamespace(
    text="The current speaker has produced enough meaningful words for interruption."
)
CAUSE = frozenset({InterruptCause.FACTUAL_CONTRADICTION})
def test_high_provocation_lowers_threshold_but_still_requires_cause() -> None:
    high = InterruptContext(CAUSE, candidate_score=1.0, alignment_order_bias=-1)
    low = InterruptContext(CAUSE, candidate_score=1.0, alignment_order_bias=-1)
    high_decision = may_interrupt(candidate(9, 9), CURRENT, high)
    low_decision = may_interrupt(candidate(2, 2), CURRENT, low)
    assert high_decision.threshold < low_decision.threshold
    assert high_decision.allowed and not low_decision.allowed
    no_cause = InterruptContext(frozenset(), 10, -1)
    assert may_interrupt(candidate(10, 10), CURRENT, no_cause).reason is DecisionReason.NO_CAUSE
def test_cooldown_and_one_interrupt_limit_are_absolute() -> None:
    cooldown = InterruptContext(CAUSE, 10, -1, cooldown_active=True)
    used = InterruptContext(CAUSE, 10, -1, interrupts_used=1)
    assert may_interrupt(candidate(10, 10), CURRENT, cooldown).reason is DecisionReason.COOLDOWN
    assert may_interrupt(candidate(10, 10), CURRENT, used).reason is DecisionReason.LIMIT
