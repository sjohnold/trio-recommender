import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.contracts import Language
from trio.language.detector import detect_language


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Это пример, потому что для проверки можно взять только слова.",
            Language.RU,
        ),
        (
            "This is the example because the result can also be checked.",
            Language.EN,
        ),
        (
            "Ovo je primer zato što se rezultat može proveriti kada treba.",
            Language.SR,
        ),
        (
            "Ово је пример зато што се резултат може проверити када треба.",
            Language.SR,
        ),
    ],
)
def test_detects_supported_languages(text: str, expected: Language) -> None:
    result = detect_language(text)
    assert result.language is expected
    assert 0.5 <= result.confidence <= 1


@pytest.mark.parametrize("text", ["да", "to be", "1234 !?", "ovo это this test"])
def test_short_or_ambiguous_text_is_unknown(text: str) -> None:
    result = detect_language(text)
    assert result.language is None
    assert 0 <= result.confidence < 0.5
