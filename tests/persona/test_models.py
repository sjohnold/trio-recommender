import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.persona.models import AlignmentPolicyKey, PersonaConfig, PersonaStats

VALUES = {
    "energy": 1,
    "openness": 10,
    "nerve": 5,
    "sharpness": 5,
    "reasoning": 5,
    "provocation": 5,
    "attunement": 5,
}


def test_stats_are_immutable_and_normalized() -> None:
    stats = PersonaStats(**VALUES)
    assert stats.normalized("energy") == -1
    assert stats.normalized("openness") == 1
    with pytest.raises(ValidationError):
        stats.energy = 6


def test_unknown_stat_is_explicit() -> None:
    with pytest.raises(KeyError, match="charisma"):
        PersonaStats(**VALUES).normalized("charisma")


def test_alignment_is_a_separate_policy_key() -> None:
    stats = PersonaStats(**VALUES)
    config = PersonaConfig(
        role="empath",
        name="Mira",
        stats=stats,
        alignment=AlignmentPolicyKey.NEUTRAL_GOOD,
    )
    assert config.stats is stats
    assert config.alignment is AlignmentPolicyKey.NEUTRAL_GOOD
    assert "alignment" not in PersonaStats.model_fields


def test_models_do_not_import_orchestrator() -> None:
    module = sys.modules["trio.persona.models"]
    assert all("orchestrator" not in value for value in module.__dict__ if isinstance(value, str))
