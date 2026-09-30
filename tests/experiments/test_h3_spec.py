import json
from pathlib import Path

SPEC = json.loads((Path(__file__).parents[2] / "experiments/H3_modes.json").read_text())
CONDITIONS = SPEC["conditions"]


def by_language(language):
    return [item for item in CONDITIONS if item["language"] == language]


def test_each_language_has_full_pipeline_a_and_b_memory_pair():
    for language in ("ru", "en", "sr"):
        conditions = by_language(language)
        assert [(item["mode"], item["role_memory"]) for item in conditions] == [
            ("A", "not_applicable"), ("B", "enabled"), ("B", "disabled"),
        ]
        assert all(item["full_pipeline"] for item in conditions)


def test_b_memory_ablation_changes_only_role_memory_and_id():
    for language in ("ru", "en", "sr"):
        with_memory, without_memory = by_language(language)[1:]
        ignored = {"condition_id", "role_memory"}
        controlled = lambda item: {key: value for key, value in item.items()
                                   if key not in ignored}
        assert controlled(with_memory) == controlled(without_memory)


def test_scenarios_stats_limits_seeds_and_hardware_are_controlled():
    assert len({item["token_limit"] for item in CONDITIONS}) == 1
    assert len({json.dumps(item["persona_stats"], sort_keys=True)
                for item in CONDITIONS}) == 1
    assert SPEC["profile"] == "Base"
    assert {"a_pragmatist", "a_logician", "a_empath", "b_actor", "state"} == set(
        SPEC["model_digests"]
    )


def test_registered_comparisons_cover_required_outcomes():
    outcomes = CONDITIONS[0]["outcomes"]
    assert outcomes["primary"] == "a_vs_b_with_memory"
    assert set(outcomes["secondary"]) == {
        "b_with_vs_without_memory", "persona_diversity", "drift", "failures", "latency",
    }
    assert all(item["outcomes"] == outcomes for item in CONDITIONS)
