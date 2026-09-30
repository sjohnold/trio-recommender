import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
from accept_languages import CASES, accept_languages
TEXTS = {
    "ru": "Это русский текст о городе, погоде, реке и важном решении.",
    "en": "This is an English text about a city, weather, a river, and a decision.",
    "sr-Latn": "Ovo je srpski tekst o gradu, vremenu, reci, mleku i važnoj odluci.",
    "sr-Cyrl": "Ово је српски текст о граду, времену, реци, млеку и важној одлуци.",
}
def matrix():
    return [
        {
            "case": case, "mode": mode, "text": TEXTS[case],
            "model_digest": f"sha256:{mode.lower()}{case}", "latency_ms": 250,
        }
        for mode in ("A", "B") for case in CASES
    ]


def test_complete_mode_language_matrix_has_separate_results():
    result = accept_languages(matrix())
    assert result.passed, result.reasons
    assert len(result.rows) == 8
    assert {(row.mode, row.case) for row in result.rows} == {
        (mode, case) for mode in ("A", "B") for case in CASES
    }
    assert all(row.model_digest and row.latency_ms == 250 for row in result.rows)


def test_mixed_script_and_wrong_variant_are_injected_and_detected():
    evidence = matrix()
    evidence += [
        {
            "case": "sr-Latn", "mode": "A",
            "text": "Ovo je srpski tekst о времену, реци и млеку.",
            "model_digest": "sha256:mixed", "latency_ms": 100,
            "injection": "mixed_script",
        },
        {
            "case": "sr-Latn", "mode": "B",
            "text": "Dijete pije mlijeko dok vrijeme donosi snijeg; rijeka, lijep čovjek i pjesma ostaju tema.",
            "model_digest": "sha256:variant", "latency_ms": 100,
            "injection": "variant_drift",
        },
    ]
    result = accept_languages(evidence)
    assert result.passed, result.reasons
    injected = [row for row in result.rows if row.injection]
    assert [row.injection for row in injected] == ["mixed_script", "variant_drift"]
    assert all(row.injection in row.violations for row in injected)


def test_missing_matrix_or_injection_failure_is_explicit():
    evidence = matrix()[:-1]
    evidence.append({
        "case": "sr-Latn", "mode": "A", "text": TEXTS["sr-Latn"],
        "model_digest": "sha256:x", "latency_ms": 1, "injection": "mixed_script",
    })
    reasons = accept_languages(evidence).reasons
    assert "matrix_incomplete" in reasons
    assert any(reason.endswith("injection_not_detected") for reason in reasons)
