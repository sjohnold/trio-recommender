import sys
from itertools import product
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.persona.ablation import AblationConfig
from trio.persona.generation import map_generation
from trio.persona.models import PersonaStats

PROFILES = [
    SimpleNamespace(name="Mini", num_ctx=2048),
    SimpleNamespace(name="Base", num_ctx=4096),
    SimpleNamespace(name="Plus", num_ctx=8192),
    SimpleNamespace(name="Max", num_ctx=8192),
]


def stats(energy=5, openness=5, nerve=5, **changes) -> PersonaStats:
    values = {
        "energy": energy,
        "openness": openness,
        "nerve": nerve,
        "sharpness": 5,
        "reasoning": 5,
        "provocation": 5,
        "attunement": 5,
    } | changes
    return PersonaStats(**values)


def test_all_effective_stat_combinations_stay_bounded_and_deterministic() -> None:
    for profile in PROFILES:
        for energy, openness, nerve in product(range(1, 11), repeat=3):
            persona = stats(energy, openness, nerve)
            options = map_generation(persona, profile)
            assert options == map_generation(persona, profile)
            assert 0.4 <= options.temperature <= 1.0
            assert 0.04 <= options.min_p <= 0.15
            assert 1.05 <= options.repeat_penalty <= 1.25
            assert 64 <= options.num_predict <= 384
            assert options.num_ctx == profile.num_ctx


def test_monotonic_directions_hold_for_every_value() -> None:
    profile = PROFILES[1]
    energy = [map_generation(stats(energy=value), profile) for value in range(1, 11)]
    openness = [
        map_generation(stats(openness=value), profile) for value in range(1, 11)
    ]
    nerve = [map_generation(stats(nerve=value), profile) for value in range(1, 11)]
    assert [item.num_predict for item in energy] == sorted(
        item.num_predict for item in energy
    )
    assert [item.temperature for item in openness] == sorted(
        item.temperature for item in openness
    )
    assert [item.min_p for item in openness] == sorted(
        (item.min_p for item in openness), reverse=True
    )
    assert [item.repeat_penalty for item in nerve] == sorted(
        item.repeat_penalty for item in nerve
    )


def test_disabled_stage_uses_defaults_for_all_profiles() -> None:
    config = AblationConfig(stage1=False).validate()
    for profile in PROFILES:
        options = map_generation(
            stats(energy=10, openness=10, nerve=10),
            profile,
            enabled=config.stage1,
        )
        assert (
            options.temperature,
            options.min_p,
            options.repeat_penalty,
            options.num_predict,
            options.num_ctx,
        ) == (0.7, 0.08, 1.12, 224, profile.num_ctx)
