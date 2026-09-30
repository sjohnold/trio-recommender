import json
from pathlib import Path

CATALOG = Path(__file__).parents[2] / "data/persona/style_rules.json"
STATS = {
    "energy",
    "openness",
    "nerve",
    "sharpness",
    "reasoning",
    "provocation",
    "attunement",
}


def load() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def find(stat: str, score: int) -> list[dict]:
    return [
        rule
        for rule in load()["rules"]
        if rule["stat"] == stat and rule["range"][0] <= score <= rule["range"][1]
    ]


def test_catalog_schema_covers_all_stats_without_alignment() -> None:
    data = load()
    assert data["version"] == "1.0.0"
    assert {rule["stat"] for rule in data["rules"]} == STATS
    assert len({rule["id"] for rule in data["rules"]}) == len(data["rules"])
    for rule in data["rules"]:
        assert set(rule) == {
            "id", "stat", "range", "languages", "require", "forbid", "priority"
        }
        assert 1 <= rule["range"][0] <= rule["range"][1] <= 10
        assert rule["languages"] == ["ru", "en", "sr"]
        assert rule["require"]
        assert isinstance(rule["priority"], int)
    assert "alignment" not in json.dumps(data)


def test_required_threshold_behaviors() -> None:
    sharp = find("sharpness", 3)
    provoke = find("provocation", 8)
    attune = find("attunement", 7)
    assert any("mitigate_disagreement" in rule["require"] for rule in sharp)
    assert any("name_contested_claim" in rule["require"] for rule in provoke)
    assert any("reference_other_speaker" in rule["require"] for rule in attune)
