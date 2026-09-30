import json
from pathlib import Path

SPEC = json.loads(
    (Path(__file__).parents[2] / "experiments/H2_persona_pipeline.json").read_text()
)
CONDITIONS = SPEC["conditions"]


def test_pipeline_conditions_are_cumulative_and_isolate_each_stage():
    expected = [
        ("baseline", {"stage1": False, "stage2": False, "stage3": False}),
        ("s1", {"stage1": True, "stage2": False, "stage3": False}),
        ("s1_s2", {"stage1": True, "stage2": True, "stage3": False}),
        ("s1_s2_s3", {"stage1": True, "stage2": True, "stage3": True}),
    ]
    assert [(item["condition_id"], item["ablation"]) for item in CONDITIONS] == expected
    for index, (before, after) in enumerate(zip(CONDITIONS, CONDITIONS[1:]), 1):
        changed = {key for key in before["ablation"]
                   if before["ablation"][key] != after["ablation"][key]}
        assert changed == {f"stage{index}"}


def test_models_preset_scenario_and_unconditional_rules_are_controlled():
    assert len({item["persona_preset"] for item in CONDITIONS}) == 1
    assert all(item["name"] == "persona_engine" for item in CONDITIONS)
    forbidden_overrides = {"model_digests", "semantic_scenario_id"}
    assert all(forbidden_overrides.isdisjoint(item) for item in CONDITIONS)
    rules = [tuple(item["unconditional_rules"]) for item in CONDITIONS]
    assert len(set(rules)) == 1 and rules[0]


def test_every_condition_registers_the_same_outcomes():
    expected = {
        "primary": "drift_onset_turn",
        "secondary": ["feature_distance_auc", "language_integrity", "latency"],
    }
    assert all(item["outcomes"] == expected for item in CONDITIONS)
