import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.persona.validation import PointBudgetError, validate_persona


def persona(stats: dict[str, int]) -> dict:
    defaults = {
        "energy": 5,
        "openness": 5,
        "nerve": 5,
        "sharpness": 5,
        "reasoning": 5,
        "provocation": 5,
        "attunement": 5,
    }
    defaults.update(stats)
    return {
        "name": "Ada",
        "role": "logician",
        "alignment": "lawful_neutral",
        "stats": defaults,
    }


def test_all_ten_bonus_points_are_allowed() -> None:
    result = validate_persona(persona({"energy": 10, "openness": 10}))
    assert result.stats.energy == 10


def test_eleven_points_are_rejected_with_budget_details() -> None:
    with pytest.raises(PointBudgetError) as caught:
        validate_persona(
            persona({"energy": 10, "openness": 10, "nerve": 6})
        )
    assert (caught.value.used, caught.value.available) == (11, 10)


def test_lowering_stats_does_not_create_points() -> None:
    with pytest.raises(PointBudgetError):
        validate_persona(
            persona({"energy": 1, "openness": 10, "nerve": 10, "sharpness": 6})
        )


def test_seven_tens_are_impossible() -> None:
    with pytest.raises(PointBudgetError) as caught:
        validate_persona(persona({name: 10 for name in persona({})["stats"]}))
    assert caught.value.used == 35
