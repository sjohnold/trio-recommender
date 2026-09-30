import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.persona.generation import map_generation
from trio.persona.models import PersonaStats

BASE = {
    "energy": 5,
    "openness": 5,
    "nerve": 5,
    "sharpness": 5,
    "reasoning": 5,
    "provocation": 5,
    "attunement": 5,
}
PROFILE = SimpleNamespace(num_ctx=4096)


def stats(**changes) -> PersonaStats:
    values = BASE | changes
    return PersonaStats(**values)


def test_mapper_is_deterministic_and_profile_owns_context() -> None:
    first = map_generation(stats(openness=9), PROFILE)
    second = map_generation(stats(openness=9), PROFILE)
    assert first == second
    assert first.num_ctx == 4096


def test_all_results_are_bounded() -> None:
    low = map_generation(stats(energy=1, openness=1, nerve=1), PROFILE)
    high = map_generation(stats(energy=10, openness=10, nerve=10), PROFILE)
    for options in (low, high):
        assert 0.4 <= options.temperature <= 1.0
        assert 0.04 <= options.min_p <= 0.15
        assert 1.05 <= options.repeat_penalty <= 1.25
        assert 64 <= options.num_predict <= 384


def test_nerve_increases_but_bounds_repeat_penalty() -> None:
    low = map_generation(stats(nerve=1), PROFILE)
    high = map_generation(stats(nerve=10), PROFILE)
    assert 1.05 <= low.repeat_penalty < high.repeat_penalty <= 1.25


def test_disabled_stage_returns_bases_independent_of_stats() -> None:
    low = map_generation(stats(energy=1, openness=1, nerve=1), PROFILE, False)
    high = map_generation(stats(energy=10, openness=10, nerve=10), PROFILE, False)
    assert low == high
    assert (low.temperature, low.min_p, low.repeat_penalty, low.num_predict) == (
        0.7,
        0.08,
        1.12,
        224,
    )
