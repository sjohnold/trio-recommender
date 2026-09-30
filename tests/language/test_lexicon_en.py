import json
import unicodedata
from pathlib import Path

LEXICON = Path(__file__).parents[2] / "data/lexicons/en.json"
REQUIRED = {
    "modal",
    "stance",
    "disagreement",
    "softener",
    "intensifier",
    "causal",
    "analogy",
    "affiliation",
}


def load() -> dict:
    return json.loads(LEXICON.read_text(encoding="utf-8"))


def test_schema_is_normalized_and_english_specific() -> None:
    data = load()
    assert data["language"] == "en"
    assert set(data["categories"]) == REQUIRED
    for entries in data["categories"].values():
        assert entries
        for entry in entries:
            pattern = entry["pattern"]
            assert pattern == unicodedata.normalize("NFC", pattern.casefold().strip())
            assert set(entry) == {"pattern", "kind", "weight"}
            assert 0 < entry["weight"] <= 1


def test_request_and_epistemic_could_are_distinct() -> None:
    entries = load()["categories"]["modal"]
    by_pattern = {entry["pattern"]: entry["kind"] for entry in entries}
    assert by_pattern["could be"] == "epistemic-modal"
    assert by_pattern["could have"] == "epistemic-modal"
    assert by_pattern["could you"] == "request-modal"


def test_contextual_well_and_i_think_rules() -> None:
    data = load()["categories"]
    assert {
        (entry["pattern"], entry["kind"])
        for entry in data["softener"] + data["stance"]
    } >= {
        ("well,", "discourse-initial"),
        ("i think", "initial-frame"),
    }
