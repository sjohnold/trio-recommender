import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.metrics.tokenize import tokenize


def lock(language):
    return SimpleNamespace(language=language)


def test_empty_text_is_deterministic():
    first = tokenize("", lock("en"))
    assert first == tokenize("", lock("en"))
    assert first.original == ""
    assert first.tokens == first.lemmas == first.sentences == first.script_spans == ()
    assert first.sr_canonical is None


def test_abbreviations_numbers_and_sentences():
    text = "Dr. Smith has 3.14 points. Is that 10,5? Yes!"
    document = tokenize(text, lock("en"))
    assert document.original == text
    assert document.sentences == (
        "Dr. Smith has 3.14 points.", "Is that 10,5?", "Yes!",
    )
    assert "3.14" in document.tokens and "10,5" in document.tokens
    assert document.lemmas[:2] == ("dr", "smith")


def test_russian_and_mixed_script_spans():
    document = tokenize("Привет, Trio 2026!", lock("ru"))
    assert document.tokens == ("Привет", "Trio", "2026")
    assert [(span.script, span.text) for span in document.script_spans] == [
        ("Cyrl", "Привет"), ("Latn", "Trio"),
    ]


def test_serbian_cyrillic_has_latin_canonical_copy():
    text = "Људи кажу: лепо време."
    document = tokenize(text, lock("sr"))
    assert document.original == text
    assert document.sr_canonical == "Ljudi kažu: lepo vreme."
    assert document.lemmas == ("ljudi", "kažu", "lepo", "vreme")
    assert all(span.script == "Cyrl" for span in document.script_spans)


def test_hyphen_and_apostrophe_stay_in_tokens():
    text = "по-видимому don't Cafe\u0301"
    document = tokenize(text, lock("en"))
    assert document.original == text
    assert document.tokens == ("по-видимому", "don't", "Cafe")
