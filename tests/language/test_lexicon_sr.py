import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.language.serbian import normalize_serbian

LEXICON = Path(__file__).parents[2] / "data/lexicons/sr.json"


def load() -> dict:
    return json.loads(LEXICON.read_text(encoding="utf-8"))


def matched_kinds(text: str, category: str) -> set[str]:
    normalized = normalize_serbian(text).latin.casefold()
    entries = load()["categories"][category]
    return {
        entry["kind"]
        for entry in entries
        if re.search(rf"(?<!\w){re.escape(entry['pattern'])}(?!\w)", normalized)
    }


def test_schema_uses_canonical_serbian_latin() -> None:
    data = load()
    assert (data["language"], data["normalization"]) == ("sr", "sr-Latn")
    assert set(data["categories"]) == {
        "pragmatic",
        "disagreement",
        "affiliation",
        "variant",
    }
    for entries in data["categories"].values():
        assert entries
        for entry in entries:
            pattern = entry["pattern"]
            assert pattern == unicodedata.normalize("NFC", pattern.casefold().strip())
            assert 0 < entry["weight"] <= 1


def test_ekavian_and_ijekavian_examples_are_separate() -> None:
    assert matched_kinds("Lepo vreme.", "variant") == {"ekavian"}
    assert matched_kinds("Lijepo vrijeme.", "variant") == {"ijekavian"}


def test_cyrillic_matches_after_script_report_is_preserved() -> None:
    text = "Разумем поенту, али се не слажем."
    normalized = normalize_serbian(text)
    assert normalized.original == text
    assert "softener" in matched_kinds(text, "pragmatic")
    assert "direct" in matched_kinds(text, "disagreement")
