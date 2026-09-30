"""Small deterministic RU/EN/SR language detector."""

import re
from dataclasses import dataclass

from trio.contracts import Language

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_MARKERS = {
    Language.RU: frozenset(
        "это что потому если когда есть для как который можно чтобы также только уже очень".split()
    ),
    Language.EN: frozenset(
        "the this that because if when is are for with which can would also only very".split()
    ),
    Language.SR: frozenset(
        (
            "ovo što zato jer ako kada nije jeste koji može ali ili da se su sam "
            "ово што зато јер ако када није јесте који може али или да се су сам"
        ).split()
    ),
}


@dataclass(frozen=True, slots=True)
class LanguageDetection:
    language: Language | None
    confidence: float


def detect_language(text: str) -> LanguageDetection:
    tokens = [token.casefold() for token in _WORD.findall(text)]
    if len(tokens) < 4:
        return LanguageDetection(None, 0.0)
    scores = {
        language: sum(token in markers for token in tokens)
        for language, markers in _MARKERS.items()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    (best_language, best), (_, second) = ranked[:2]
    total = sum(scores.values())
    confidence = (best / total) * min(1.0, best / 4) if total else 0.0
    if best < 2 or best - second < 1:
        return LanguageDetection(None, min(confidence, 0.49))
    return LanguageDetection(best_language, round(confidence, 3))

