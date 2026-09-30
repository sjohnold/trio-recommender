import json
import re
import unicodedata
from pathlib import Path

LEXICON = Path(__file__).parents[2] / "data/lexicons/ru.json"
REQUIRED = {
    "hedges",
    "disagreement",
    "softeners",
    "intensifiers",
    "causal",
    "analogy",
    "affiliation",
}


def load() -> dict:
    return json.loads(LEXICON.read_text(encoding="utf-8"))


def matches(pattern: str, text: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(pattern)}(?!\w)", text.casefold()))


def test_schema_categories_and_normalization() -> None:
    data = load()
    assert data["language"] == "ru"
    assert set(data["categories"]) == REQUIRED
    for entries in data["categories"].values():
        assert entries
        for entry in entries:
            pattern = entry["pattern"]
            assert pattern == unicodedata.normalize("NFC", pattern.casefold().strip())
            assert "  " not in pattern
            assert entry["kind"] in {"token", "phrase", "frame"}
            assert 0 < entry["weight"] <= 1


def test_positive_examples_match_all_categories() -> None:
    text = (
        "Вероятно, это неверно. Понимаю ход мысли, но это безусловно важно, "
        "поскольку это как важный момент."
    ).casefold()
    for entries in load()["categories"].values():
        assert any(matches(entry["pattern"], text) for entry in entries)


def test_patterns_respect_word_boundaries() -> None:
    assert not matches("согласен", "несогласенность")
    assert not matches("явно", "неявность")
