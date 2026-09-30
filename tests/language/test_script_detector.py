import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.language.script_detector import DetectedScript, Span, detect_script


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Привет, мир!", DetectedScript.CYRILLIC),
        ("Zdravo, čoveče!", DetectedScript.LATIN),
        ("Здраво, човече!", DetectedScript.CYRILLIC),
        ("Привет zdravo", DetectedScript.MIXED),
        ("123 — !?", DetectedScript.UNKNOWN),
    ],
)
def test_detects_scripts_without_punctuation_noise(text, expected) -> None:
    assert detect_script(text, []).script is expected


def test_ignores_urls_code_and_marked_quotes() -> None:
    text = "Текст https://example.com/latin `code` \n> quoted latin\nещё"
    report = detect_script(text, [])
    assert report.script is DetectedScript.CYRILLIC
    assert report.ignored_characters > 0


def test_ignores_caller_span() -> None:
    text = "Привет quoted"
    report = detect_script(text, [Span(7, len(text))])
    assert report.script is DetectedScript.CYRILLIC


def test_invalid_span_is_rejected() -> None:
    with pytest.raises(ValueError):
        detect_script("text", [Span(5, 6)])
