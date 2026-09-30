import json
from itertools import permutations
from pathlib import Path

SPEC = json.loads((Path(__file__).parents[2] / "experiments/H5_languages.json").read_text())
CONDITIONS = SPEC["conditions"]


def test_versions_are_separately_authored_and_semantically_keyed():
    assert set(SPEC["authored_texts"]) == {"ru", "en", "sr"}
    texts = {
        language: tuple(event["text"] for event in authored["events"])
        for language, authored in SPEC["authored_texts"].items()
    }
    assert len(set(texts.values())) == 3
    assert "runtime_translation" not in json.dumps(SPEC)


def test_language_conditions_are_identical_except_lock_and_id():
    ignored = {"condition_id", "language", "script"}
    controlled = lambda item: {key: value for key, value in item.items()
                               if key not in ignored}
    assert len({json.dumps(controlled(item), sort_keys=True)
                for item in CONDITIONS}) == 1
    assert {(item["language"], item["script"]) for item in CONDITIONS} == {
        ("ru", "Cyrillic"), ("en", "Latin"), ("sr", "Latin"),
    }


def test_all_language_orders_are_counterbalanced():
    orders = [tuple(order) for order in SPEC["counterbalance_orders"]]
    assert set(orders) == set(permutations(("ru", "en", "sr")))
    assert SPEC["repetitions"] % len(orders) == 0
    for position in range(3):
        assert {language: sum(order[position] == language for order in orders)
                for language in ("ru", "en", "sr")} == {"ru": 2, "en": 2, "sr": 2}


def test_primary_results_are_separate_and_outcomes_cover_each_language():
    assert all(item["aggregation"] == "separate_by_language" for item in CONDITIONS)
    assert all(item["outcomes"]["primary"] == "language_specific_drift_onset"
               for item in CONDITIONS)
    assert set(CONDITIONS[0]["outcomes"]["secondary"]) == {
        "feature_distance", "language_integrity", "latency",
    }
    assert "pooled_mean" not in json.dumps(SPEC)
