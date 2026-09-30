import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.contracts import Language, Role
from trio.language.contracts import LanguageLock
from trio.persona.models import AlignmentPolicyKey, PersonaStats
from trio.persona.selector import (
    InsufficientVoiceExamplesWarning, rank_examples, select_examples,
)
from trio.persona.voice_query import VoiceQuery

STATS = PersonaStats(
    energy=5, openness=5, nerve=5, sharpness=5,
    reasoning=5, provocation=5, attunement=5,
)
LOCK = LanguageLock(language=Language.EN)


@dataclass(frozen=True)
class Example:
    id: str
    text: str
    topic: str
    language: LanguageLock = LOCK
    role: Role = Role.LOGICIAN
    stats: PersonaStats = STATS
    alignment: AlignmentPolicyKey = AlignmentPolicyKey.TRUE_NEUTRAL


def query(limit=3) -> VoiceQuery:
    return VoiceQuery(
        language=LOCK, role=Role.LOGICIAN, stats=STATS,
        alignment=AlignmentPolicyKey.TRUE_NEUTRAL, limit=limit,
    )


def test_top_k_is_stable_diverse_and_deduplicated() -> None:
    candidates = [
        Example("b", "Same text", "facts"),
        Example("a", " Same   TEXT ", "facts"),
        Example("d", "Another", "facts"),
        Example("c", "Question", "logic"),
        Example("e", "Feeling", "dialogue"),
    ]
    result = select_examples(query(), candidates)
    assert [item.id for item in result] == ["a", "c", "e"]
    assert len({item.topic for item in result}) == 3


def test_language_and_role_are_hard_filters() -> None:
    candidates = [
        Example("ok", "One", "topic"),
        Example("ru", "Два", "other", language=LanguageLock(language=Language.RU)),
        Example("role", "Three", "third", role=Role.EMPATH),
    ]
    with pytest.warns(InsufficientVoiceExamplesWarning):
        result = select_examples(query(2), candidates)
    assert [item.id for item in result] == ["ok"]


def test_shortage_is_visible_as_warning() -> None:
    with pytest.warns(InsufficientVoiceExamplesWarning, match="only 0 of 2"):
        assert select_examples(query(2), []) == []


def test_explainable_ranking_exposes_score_and_diversity_decision() -> None:
    candidates = [
        Example("a", "First", "facts"),
        Example("b", "Second", "facts"),
        Example("c", "Third", "logic"),
    ]
    ranking = rank_examples(query(2), candidates)
    assert [item.rank for item in ranking] == [1, 2, 3]
    assert [item.example.id for item in ranking if item.selected] == ["a", "c"]
    assert all(item.distance == 0 for item in ranking)
