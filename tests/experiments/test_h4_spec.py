import json
from pathlib import Path

SPEC = json.loads(
    (Path(__file__).parents[2] / "experiments/H4_agreement_threshold.json").read_text()
)
CONDITIONS = SPEC["conditions"]


def test_provocation_sweep_is_complete_and_sharpness_is_fixed():
    assert [item["provocation"] for item in CONDITIONS] == list(range(1, 11))
    assert {item["sharpness"] for item in CONDITIONS} == {5}
    assert all(item["name"] == "provocation_sweep" for item in CONDITIONS)


def test_substantive_disagreement_requires_target_ground_and_reason():
    definition = {
        "required": ["target", "ground", "reason"],
        "plain_negation_counts": False,
    }
    assert all(item["disagreement_definition"] == definition for item in CONDITIONS)


def test_threshold_is_first_zone_below_point_two_with_bootstrap_ci():
    threshold = {
        "rate_below": 0.2, "interval": "bootstrap_ci", "selection": "first_zone",
    }
    assert all(item["threshold"] == threshold for item in CONDITIONS)


def test_authored_scenarios_have_verifiable_disagreement_opportunities():
    for authored in SPEC["authored_texts"].values():
        kinds = {event["kind"] for event in authored["events"]}
        assert {"evidence", "correction"} <= kinds
        assert authored["counterarguments"]
    assert SPEC["expected_opportunities"]["disagreement"] > 0
