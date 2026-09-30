import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.contracts import Language
from trio.language.contracts import LanguageLock, SerbianVariant
from trio.language.script_detector import DetectedScript
from trio.language.serbian import check_variant, normalize_serbian


def test_cyrillic_normalization_preserves_original_and_content() -> None:
    result = normalize_serbian("Љубав, њена ђачка реч!")
    assert result.original == "Љубав, њена ђачка реч!"
    assert result.latin == "Ljubav, njena đačka reč!"
    assert result.source_script is DetectedScript.CYRILLIC


@pytest.mark.parametrize(
    ("text", "variant"),
    [
        ("Mleko, lepo vreme i dete.", SerbianVariant.EKAVIAN),
        ("Mlijeko, lijepo vrijeme i dijete.", SerbianVariant.IJEKAVIAN),
    ],
)
def test_detects_variant_from_multiple_markers(text, variant) -> None:
    lock = LanguageLock(language=Language.SR, variant=variant)
    report = check_variant(text, lock)
    assert report.observed is variant
    assert report.conforms is True


def test_one_lexeme_does_not_decide_variant_or_neighbor_language() -> None:
    lock = LanguageLock(language=Language.SR)
    variant = check_variant("Mlijeko, mlijeko.", lock)
    neighbor = check_variant("Tisuća.", lock)
    assert variant.observed is None
    assert neighbor.observed is None
    assert neighbor.neighbor_score == 1


def test_mixed_variant_is_separate_failure() -> None:
    report = check_variant("Mleko je lijepo.", LanguageLock(language=Language.SR))
    assert report.mixed
    assert report.observed is None
    assert report.conforms is False


def test_non_serbian_lock_is_rejected() -> None:
    with pytest.raises(ValueError):
        check_variant("text", LanguageLock(language=Language.EN))
