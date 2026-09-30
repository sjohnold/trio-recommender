import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.contracts import Language, Role
from trio.language.contracts import LanguageLock
from trio.persona.distance import DISTANCE_VERSION, STAT_WEIGHTS
from trio.persona.distance import HardFilterMismatch, score_example
from trio.persona.models import AlignmentPolicyKey, PersonaStats
from trio.persona.voice_query import VoiceQuery


def stats(value: int) -> PersonaStats:
    return PersonaStats(**{name: value for name in STAT_WEIGHTS})


@dataclass(frozen=True)
class Example:
    language: LanguageLock
    role: Role
    stats: PersonaStats
    alignment: AlignmentPolicyKey


LOCK = LanguageLock(language=Language.EN)
QUERY = VoiceQuery(
    language=LOCK,
    role=Role.LOGICIAN,
    stats=stats(1),
    alignment=AlignmentPolicyKey.LAWFUL_GOOD,
)


def example(**changes) -> Example:
    values = {
        "language": LOCK,
        "role": Role.LOGICIAN,
        "stats": stats(1),
        "alignment": AlignmentPolicyKey.LAWFUL_GOOD,
    } | changes
    return Example(**values)


def test_weights_are_versioned_and_normalized() -> None:
    assert DISTANCE_VERSION == "1.0.0"
    assert sum(STAT_WEIGHTS.values()) == pytest.approx(1)


def test_zero_distance_is_minimum_and_opposite_stats_are_one() -> None:
    assert score_example(QUERY, example()) == 0
    assert score_example(QUERY, example(stats=stats(10))) == 1


def test_alignment_adds_a_discrete_penalty() -> None:
    mismatch = example(alignment=AlignmentPolicyKey.CHAOTIC_EVIL)
    assert score_example(QUERY, mismatch) == 0.25


@pytest.mark.parametrize(
    "changes",
    [
        {"language": LanguageLock(language=Language.RU)},
        {"role": Role.EMPATH},
    ],
)
def test_hard_filters_cannot_be_compensated_by_stats(changes) -> None:
    with pytest.raises(HardFilterMismatch):
        score_example(QUERY, example(**changes))
