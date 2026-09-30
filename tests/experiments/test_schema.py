import json
from pathlib import Path
import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[2]
SCHEMA = json.loads((ROOT / "schemas/experiment.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


def experiment():
    authored = {
        "events": [{"turn": 1, "kind": "user", "text": "Authored text"}],
        "counterarguments": ["Authored counterargument"],
    }
    return {
        "id": "counter-001-en",
        "semantic_scenario_id": "counter-001",
        "hypotheses": ["H1", "H2", "H3", "H4", "H5"],
        "language": "en",
        "seed": 42,
        "repetitions": 20,
        "profile": "Base",
        "mode": "A",
        "model_digests": {
            "pragmatist": "sha256:12345678",
            "state": "sha256:abcdef12",
        },
        "ablation": {"stage1": True, "stage2": True, "stage3": False},
        "conditions": [{
            "name": "provocation_sweep",
            "provocation": 7,
            "persona_preset": "default-trio@1.0.0",
        }],
        "authored_texts": {"ru": authored, "en": authored, "sr": authored},
        "expected_opportunities": {
            "disagreement": 3, "counterargument_response": 2, "turn_claim": 3,
        },
    }


def errors(value):
    return list(VALIDATOR.iter_errors(value))


def test_valid_scenario_covers_h1_to_h5_and_reproducibility():
    assert errors(experiment()) == []


def test_all_three_authored_languages_are_required():
    value = experiment()
    del value["authored_texts"]["sr"]
    assert any(error.validator == "required" for error in errors(value))


@pytest.mark.parametrize("mutation", ["digest", "ablation", "translation"])
def test_invalid_reproducibility_or_runtime_translation_is_rejected(mutation):
    value = experiment()
    if mutation == "digest":
        value["model_digests"]["state"] = "latest"
    elif mutation == "ablation":
        del value["ablation"]["stage2"]
    else:
        value["runtime_translation"] = True
    assert errors(value)
