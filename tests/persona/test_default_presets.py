import json
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.persona.validation import validate_persona

PRESET = Path(__file__).parents[2] / "data/presets/default-trio.json"


def test_default_trio_is_valid_and_complete() -> None:
    data = json.loads(PRESET.read_text(encoding="utf-8"))
    assert data["version"] == "1.0.0"
    assert len(data["personas"]) == 3
    personas = [validate_persona(item) for item in data["personas"]]
    assert {persona.role.value for persona in personas} == {
        "pragmatist",
        "logician",
        "empath",
    }
    assert len({persona.name for persona in personas}) == 3


def test_personas_are_pairwise_distinct() -> None:
    data = json.loads(PRESET.read_text(encoding="utf-8"))
    for left, right in combinations(data["personas"], 2):
        stat_differences = sum(
            left["stats"][name] != right["stats"][name] for name in left["stats"]
        )
        alignment_difference = left["alignment"] != right["alignment"]
        assert stat_differences >= 3 or alignment_difference
