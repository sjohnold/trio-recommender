"""Independent language, script, and Serbian-variant integrity signals."""
import re
from dataclasses import dataclass

from trio.contracts import Language
from trio.language.contracts import LanguageLock
from trio.language.detector import detect_language
from trio.language.script_detector import DetectedScript, detect_script
from trio.language.serbian import check_variant

_EXCLUDED = re.compile(
    r"```.*?```|`[^`\n]*`|https?://\S+|www\.\S+|"
    r'"[^"\n]*"|“[^”\n]*”|«[^»\n]*»|^>[^\n]*',
    re.MULTILINE | re.DOTALL,
)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class IntegrityObservation:
    expected_language: str
    detected_language: str | None
    language_confidence: float
    expected_script: str
    detected_script: str
    variant: str | None
    neighboring_variant_score: float
    reasons: tuple[str, ...]
    valid: bool


def _visible(text: str) -> str:
    return _EXCLUDED.sub(lambda match: " " * len(match.group()), text)


def language_integrity(
    text: str, lock: LanguageLock
) -> IntegrityObservation:
    visible = _visible(text)
    language = detect_language(visible)
    script = detect_script(visible, []).script
    expected_language = getattr(lock.language, "value", lock.language)
    expected_script = getattr(lock.script, "value", lock.script)
    detected_language = (
        getattr(language.language, "value", language.language)
        if language.language is not None else None
    )
    reasons = []
    if detected_language is not None and detected_language != expected_language:
        reasons.append("wrong_language")
    if script is DetectedScript.MIXED:
        reasons.append("mixed_script")
    elif script is not DetectedScript.UNKNOWN and script.value != expected_script:
        reasons.append("wrong_script")
    variant = None
    neighboring = 0.0
    if lock.language is Language.SR:
        report = check_variant(visible, lock)
        variant = getattr(report.observed, "value", report.observed)
        if report.mixed:
            reasons.append("variant_mixed")
        elif report.conforms is False:
            reasons.append("variant_drift")
        total = report.ekavian_score + report.ijekavian_score + report.neighbor_score
        neighboring = report.neighbor_score / total if total else 0.0
    return IntegrityObservation(
        expected_language, detected_language, language.confidence,
        expected_script, script.value, variant, neighboring,
        tuple(reasons), not reasons,
    )
