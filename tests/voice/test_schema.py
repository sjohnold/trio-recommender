import copy
import json
from pathlib import Path

import pytest

SCHEMA = json.loads(
    (Path(__file__).parents[2] / "schemas/voice_example.schema.json").read_text()
)
EXAMPLE = {
    "id": "en-logician-01",
    "language": {"language": "en", "script": "Latn", "variant": None},
    "role": "logician",
    "stats": {
        "energy": 5, "openness": 6, "nerve": 4, "sharpness": 5,
        "reasoning": 8, "provocation": 4, "attunement": 5,
    },
    "alignment": "lawful_neutral",
    "topic": "evidence",
    "text": (
        "The claim sounds precise, but the evidence does not yet support it. "
        "First identify the premise, then check the source, and only then draw "
        "a conclusion that another reader could verify independently."
    ),
    "source_kind": "authored",
    "review_status": "approved",
    "real_person_based": False,
    "machine_translated": False,
}

def validate(item: dict, production: bool = False) -> None:
    assert set(item) == set(SCHEMA["required"])
    assert item["source_kind"] in {"authored", "pilot"}
    assert item["review_status"] in {"draft", "reviewed", "approved", "rejected"}
    assert item["real_person_based"] is False
    assert item["machine_translated"] is False
    words = item["text"].split()
    assert 20 <= len(words) <= 120
    lock = item["language"]
    assert (
        lock == {"language": "ru", "script": "Cyrl", "variant": None}
        or lock == {"language": "en", "script": "Latn", "variant": None}
        or lock["language"] == "sr" and lock["script"] in {"Latn", "Cyrl"}
        and lock["variant"] in {"ekavian", "ijekavian"}
    )
    assert item["role"] in {"pragmatist", "logician", "empath"}
    if production:
        assert item["review_status"] == "approved"

def test_valid_approved_example_passes_production_selection() -> None:
    validate(EXAMPLE, production=True)
    assert SCHEMA["additionalProperties"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_kind", "machine_translation"),
        ("real_person_based", True),
        ("machine_translated", True),
        ("review_status", "unreviewed"),
        ("text", "too short"),
        ("language", {"language": "en", "script": "Cyrl", "variant": None}),
    ],
)
def test_prohibited_or_invalid_metadata_is_rejected(field, value) -> None:
    item = copy.deepcopy(EXAMPLE)
    item[field] = value
    with pytest.raises(AssertionError):
        validate(item, production=True)
