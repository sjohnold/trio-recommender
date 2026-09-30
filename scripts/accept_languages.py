#!/usr/bin/env python3
"""Separate RU/EN/SR-script acceptance matrix with fault injections."""
import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from trio.contracts import Language
from trio.language.contracts import LanguageLock, Script, SerbianVariant
from trio.metrics.language_integrity import language_integrity
CASES = {
    "ru": (Language.RU, Script.CYRILLIC, None),
    "en": (Language.EN, Script.LATIN, None),
    "sr-Latn": (Language.SR, Script.LATIN, SerbianVariant.EKAVIAN),
    "sr-Cyrl": (Language.SR, Script.CYRILLIC, SerbianVariant.EKAVIAN),
}
@dataclass(frozen=True, slots=True)
class MatrixRow:
    case: str
    mode: str
    model_digest: str
    script: str
    variant: str | None
    violations: tuple[str, ...]
    latency_ms: float
    injection: str | None
@dataclass(frozen=True, slots=True)
class Acceptance:
    passed: bool
    reasons: tuple[str, ...]
    rows: tuple[MatrixRow, ...]
def accept_languages(evidence) -> Acceptance:
    rows, reasons, normal = [], [], []
    for item in evidence:
        case, mode = item.get("case"), item.get("mode")
        if case not in CASES or mode not in {"A", "B"}:
            reasons.append("unsupported_matrix_row")
            continue
        language, script, variant = CASES[case]
        lock = LanguageLock(language=language, script=script, variant=variant)
        observation = language_integrity(item.get("text", ""), lock)
        injection = item.get("injection")
        result = MatrixRow(
            case, mode, item.get("model_digest", ""), script.value,
            variant.value if variant else None, observation.reasons,
            float(item.get("latency_ms", -1)), injection,
        )
        rows.append(result)
        if not result.model_digest or result.latency_ms < 0:
            reasons.append(f"{mode}:{case}:missing_evidence")
        if injection:
            if injection not in result.violations:
                reasons.append(f"{mode}:{case}:injection_not_detected")
        else:
            normal.append((mode, case))
            if result.violations:
                reasons.append(f"{mode}:{case}:{','.join(result.violations)}")
    expected = {(mode, case) for mode in ("A", "B") for case in CASES}
    if len(normal) != 8 or set(normal) != expected:
        reasons.append("matrix_incomplete")
    return Acceptance(not reasons, tuple(reasons), tuple(rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=argparse.FileType())
    result = accept_languages(json.load(parser.parse_args().evidence))
    print(json.dumps(asdict(result), ensure_ascii=False))
    raise SystemExit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
