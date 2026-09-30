import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.contracts import Language, Role
from trio.language.contracts import LanguageLock, Script
from trio.persona.models import AlignmentPolicyKey, PersonaStats
from trio.persona.voice_query import VoiceExampleScore, VoiceQuery

STATS = PersonaStats(
    energy=5, openness=6, nerve=4, sharpness=5,
    reasoning=7, provocation=3, attunement=6,
)


def query(limit=3) -> VoiceQuery:
    return VoiceQuery(
        language=LanguageLock(language=Language.SR),
        role=Role.EMPATH,
        stats=STATS,
        alignment=AlignmentPolicyKey.NEUTRAL_GOOD,
        limit=limit,
    )


@pytest.mark.parametrize("limit", [2, 3])
def test_only_two_or_three_examples_are_allowed(limit: int) -> None:
    assert query(limit).limit == limit


@pytest.mark.parametrize("limit", [0, 1, 4])
def test_invalid_limit_is_rejected(limit: int) -> None:
    with pytest.raises(ValidationError):
        query(limit)


def test_language_lock_and_role_are_hard_filters() -> None:
    value = query()
    assert value.matches_hard_filters(LanguageLock(language=Language.SR), Role.EMPATH)
    assert not value.matches_hard_filters(
        LanguageLock(language=Language.SR, script=Script.CYRILLIC),
        Role.EMPATH,
    )
    assert not value.matches_hard_filters(value.language, Role.LOGICIAN)


def test_score_is_finite_nonnegative_and_typed() -> None:
    score = VoiceExampleScore(example_id="sr-empath-01", distance=0.25, alignment_match=True)
    assert score.distance == 0.25
    for distance in (-0.1, float("inf")):
        with pytest.raises(ValidationError):
            VoiceExampleScore(example_id="x", distance=distance, alignment_match=False)
