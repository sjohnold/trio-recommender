import copy
import json
from pathlib import Path

import pytest

SCHEMA = json.loads(
    (Path(__file__).parents[2] / "schemas/persona.schema.json").read_text()
)
VALID = {
    "name": "Ada",
    "role": "logician",
    "alignment": "lawful_neutral",
    "stats": {
        "energy": 5,
        "openness": 7,
        "nerve": 4,
        "sharpness": 6,
        "reasoning": 8,
        "provocation": 3,
        "attunement": 5,
    },
}


def validate(persona: dict) -> None:
    assert set(persona) == set(SCHEMA["required"])
    assert isinstance(persona["name"], str) and persona["name"].strip()
    assert len(persona["name"]) <= SCHEMA["properties"]["name"]["maxLength"]
    assert persona["role"] in SCHEMA["properties"]["role"]["enum"]
    assert persona["alignment"] in SCHEMA["properties"]["alignment"]["enum"]
    stats_schema = SCHEMA["properties"]["stats"]
    assert set(persona["stats"]) == set(stats_schema["required"])
    for name, value in persona["stats"].items():
        rule = stats_schema["properties"][name]
        assert type(value) is int
        assert rule["minimum"] <= value <= rule["maximum"]


def test_valid_persona_passes() -> None:
    validate(VALID)
    assert SCHEMA["additionalProperties"] is False
    assert SCHEMA["properties"]["stats"]["additionalProperties"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda item: item["stats"].update(energy=4.5),
        lambda item: item["stats"].update(unknown=5),
        lambda item: item.update(role="wizard"),
    ],
)
def test_invalid_persona_is_rejected(mutate) -> None:
    persona = copy.deepcopy(VALID)
    mutate(persona)
    with pytest.raises(AssertionError):
        validate(persona)
