import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.contracts import Language
from trio.persona.models import PersonaStats
from trio.persona.rules import build_style_rules


def stats(**changes) -> PersonaStats:
    values = {
        "energy": 5, "openness": 5, "nerve": 5, "sharpness": 5,
        "reasoning": 5, "provocation": 5, "attunement": 5,
    } | changes
    return PersonaStats(**values)


def test_disabled_style_keeps_all_unconditional_rules() -> None:
    disabled = build_style_rules(stats(), Language.RU, False)
    assert len(disabled.unconditional) == 5
    assert disabled.style == ()
    assert len(disabled.lines) == 5


def test_priority_deduplication_and_small_model_limit() -> None:
    result = build_style_rules(
        stats(energy=10, openness=10, nerve=10, sharpness=10,
              reasoning=10, provocation=10, attunement=10),
        Language.EN,
        True,
    )
    assert len(result.lines) <= 8
    assert result.style[0].id == "provocation_high_target"
    constructs = [
        item for rule in result.style for item in (*rule.require, *rule.forbid)
    ]
    assert len(constructs) == len(set(constructs))
    assert not {"invented_fact", "person_target"} & set(constructs)


def test_low_sharpness_requires_mitigation_in_requested_language() -> None:
    result = build_style_rules(stats(sharpness=3), Language.SR, True)
    assert any("mitigate_disagreement" in rule.require for rule in result.style)
    assert result.unconditional[0].startswith("Kritikuj")


def test_alignment_is_not_an_argument() -> None:
    assert "alignment" not in inspect.signature(build_style_rules).parameters
