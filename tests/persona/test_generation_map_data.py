import json
from pathlib import Path

MAP = Path(__file__).parents[2] / "data/persona/generation_map.json"


def load() -> dict:
    return json.loads(MAP.read_text(encoding="utf-8"))


def value(rule: dict, stat: str, score: int) -> float:
    normalized = (score - 5.5) / 4.5
    raw = rule["base"] + rule["contributions"].get(stat, 0) * normalized
    return min(rule["max"], max(rule["min"], raw))


def test_map_is_versioned_bounded_and_complete() -> None:
    data = load()
    assert data["version"] == "1.0.0"
    assert set(data["parameters"]) == {
        "temperature",
        "min_p",
        "repeat_penalty",
        "num_predict",
    }
    for rule in data["parameters"].values():
        assert rule["min"] <= rule["base"] <= rule["max"]
        assert set(rule) == {"base", "min", "max", "contributions"}
        assert "reasoning" not in rule["contributions"]


def test_openness_monotonically_increases_variability() -> None:
    rules = load()["parameters"]
    assert value(rules["temperature"], "openness", 1) < value(
        rules["temperature"], "openness", 10
    )
    assert value(rules["min_p"], "openness", 1) > value(
        rules["min_p"], "openness", 10
    )


def test_low_energy_reduces_num_predict_with_safe_bounds() -> None:
    rule = load()["parameters"]["num_predict"]
    low = value(rule, "energy", 1)
    high = value(rule, "energy", 10)
    assert rule["min"] <= low < rule["base"] < high <= rule["max"]
    assert 64 <= low and high <= 384
