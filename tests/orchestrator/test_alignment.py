import sys
from dataclasses import fields
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trio.orchestrator.alignment import AlignmentPolicy, policy_for

ALIGNMENTS = (
    "lawful_good", "lawful_neutral", "lawful_evil",
    "neutral_good", "true_neutral", "neutral_evil",
    "chaotic_good", "chaotic_neutral", "chaotic_evil",
)


def test_all_nine_cells_are_deterministic_and_unique() -> None:
    first = [policy_for(value) for value in ALIGNMENTS]
    second = [policy_for(value) for value in ALIGNMENTS]
    assert first == second
    assert len(set(first)) == 9
    assert {(item.order_bias, item.communion_bias) for item in first} == {
        (order, communion) for order in (-1, 0, 1) for communion in (-1, 0, 1)
    }


def test_evil_cells_attack_arguments_not_people() -> None:
    prohibited = {"personal_attack", "insult", "threat", "fabricate"}
    for name in ("lawful_evil", "neutral_evil", "chaotic_evil"):
        moves = {move.value for move in policy_for(name).allowed_moves}
        assert moves.isdisjoint(prohibited)
        assert moves & {
            "argument_attack", "challenge_weak_premise", "reframe_argument"
        }


def test_policy_has_no_sampling_controls_and_rejects_unknown() -> None:
    assert {field.name for field in fields(AlignmentPolicy)} == {
        "order_bias", "communion_bias", "allowed_moves",
    }
    with pytest.raises(ValueError, match="unsupported alignment"):
        policy_for("invented")
