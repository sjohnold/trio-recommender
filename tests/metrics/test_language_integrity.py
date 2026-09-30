import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.contracts import Language
from trio.language.contracts import SerbianVariant
from trio.metrics.language_integrity import language_integrity


def lock(language, script, variant=None):
    return SimpleNamespace(
        language=language, script=SimpleNamespace(value=script), variant=variant
    )


def test_quotes_and_code_are_excluded():
    text = 'this is the point because that is clear «это потому что» `это код`'
    result = language_integrity(text, lock(Language.EN, "Latn"))
    assert result.valid
    assert result.detected_language == "en"
    assert result.detected_script == "Latn"


def test_wrong_language_and_mixed_script_have_separate_reasons():
    wrong = language_integrity(
        "это потому что есть только очень", lock(Language.EN, "Latn")
    )
    mixed = language_integrity(
        "this is the потому что mixed text", lock(Language.EN, "Latn")
    )
    assert "wrong_language" in wrong.reasons
    assert "wrong_script" in wrong.reasons
    assert "mixed_script" in mixed.reasons


def test_serbian_variant_drift_is_separate():
    result = language_integrity(
        "ovo je lijepo vrijeme, mlijeko i dijete",
        lock(Language.SR, "Latn", SerbianVariant.EKAVIAN),
    )
    assert "variant_drift" in result.reasons
    assert result.variant == "ijekavian"
    assert "wrong_language" not in result.reasons


def test_neighboring_variant_score_is_weighted_and_bounded():
    result = language_integrity(
        "ovo što zato jer tko uvjet lepo vreme",
        lock(Language.SR, "Latn", SerbianVariant.EKAVIAN),
    )
    assert 0 < result.neighboring_variant_score < 1
    assert result.expected_language == "sr"
