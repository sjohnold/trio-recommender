import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.contracts import Language, Role
from trio.persona.models import PersonaStats
from trio.persona.rules import build_style_rules

ROOT = Path(__file__).parents[2]
ANCHORS = json.loads(
    (ROOT / "data/persona/role_anchors.json").read_text(encoding="utf-8")
)
STAT_NAMES = (
    "energy",
    "openness",
    "nerve",
    "sharpness",
    "reasoning",
    "provocation",
    "attunement",
)


def stats(changed: str | None = None, score: int = 5) -> PersonaStats:
    values = {name: 5 for name in STAT_NAMES}
    if changed is not None:
        values[changed] = score
    return PersonaStats(**values)


def assert_consistent(persona: PersonaStats, language: Language) -> None:
    result = build_style_rules(persona, language, True)
    assert result.lines[: len(result.unconditional)] == result.unconditional
    assert 5 <= len(result.lines) <= 8
    required = {item for rule in result.style for item in rule.require}
    forbidden = {item for rule in result.style for item in rule.forbid}
    assert not required & forbidden
    assert all(line for line in result.lines)


def test_every_stat_value_produces_a_finite_consistent_checklist() -> None:
    for name in STAT_NAMES:
        for score in range(1, 11):
            for language in Language:
                assert_consistent(stats(name, score), language)


def test_conflict_rich_extremes_remain_consistent() -> None:
    for score in (1, 10):
        persona = PersonaStats(**{name: score for name in STAT_NAMES})
        for language in Language:
            assert_consistent(persona, language)


def test_role_anchor_is_available_for_every_role_and_language() -> None:
    roles = ANCHORS["roles"]
    for role in Role:
        for language in Language:
            patterns = roles[role.value]["patterns"][language.value]
            assert patterns
            assert all(re.compile(pattern) for pattern in patterns)
