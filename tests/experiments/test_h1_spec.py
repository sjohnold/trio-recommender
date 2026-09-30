import json
from pathlib import Path

SPEC = json.loads(
    (Path(__file__).parents[2] / "experiments/H1_prompt_only.json").read_text()
)


def condition():
    assert len(SPEC["conditions"]) == 1
    return SPEC["conditions"][0]


def keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(keys(item) for item in value))
    return set()


def test_prompt_only_has_only_authored_system_personality_text():
    item = condition()
    assert item["name"] == "prompt_only"
    assert item["personality_input"]["kind"] == "system_personality_text"
    assert item["personality_input"]["text"].strip()
    assert keys(SPEC).isdisjoint(
        {"voice_examples", "stat_sampling", "stat_checklist"}
    )


def test_all_numeric_persona_stages_are_off():
    assert SPEC["ablation"] == {
        "stage1": False, "stage2": False, "stage3": False,
    }


def test_protocol_and_registered_outcomes_are_fixed():
    item = condition()
    assert item["minimum_turns"] >= 12
    assert item["outcomes"] == {
        "primary": "drift_onset_turn",
        "secondary": ["feature_distance_trajectory"],
    }
