import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.contracts import Language
from trio.language.contracts import LanguageCheckResult, LanguageLock, Script
from trio.language.contracts import SerbianVariant


def test_serbian_defaults_to_latin_ekavian() -> None:
    lock = LanguageLock(language=Language.SR)
    assert lock.script is Script.LATIN
    assert lock.variant is SerbianVariant.EKAVIAN


@pytest.mark.parametrize(
    ("language", "script"),
    [(Language.RU, Script.CYRILLIC), (Language.EN, Script.LATIN)],
)
def test_non_serbian_defaults(language: Language, script: Script) -> None:
    lock = LanguageLock(language=language)
    assert lock.script is script
    assert lock.variant is None


@pytest.mark.parametrize(
    "values",
    [
        {"language": Language.RU, "script": Script.LATIN},
        {"language": Language.EN, "script": Script.CYRILLIC},
        {"language": Language.EN, "variant": SerbianVariant.EKAVIAN},
    ],
)
def test_invalid_combinations_are_rejected(values: dict) -> None:
    with pytest.raises(ValidationError):
        LanguageLock(**values)


def test_serbian_cyrillic_ijekavian_is_valid() -> None:
    lock = LanguageLock(
        language=Language.SR,
        script=Script.CYRILLIC,
        variant=SerbianVariant.IJEKAVIAN,
    )
    assert lock.variant is SerbianVariant.IJEKAVIAN


def test_check_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        LanguageCheckResult(valid=False, confidence=1.1)
