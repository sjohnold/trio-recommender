"""Serbian transliteration and conservative variant checks."""

import re
import unicodedata
from dataclasses import dataclass

from trio.contracts import Language
from trio.language.contracts import LanguageLock, SerbianVariant
from trio.language.script_detector import DetectedScript, detect_script

_CYRILLIC = "АБВГДЂЕЖЗИЈКЛЉМНЊОПРСТЋУФХЦЧЏШ"
_LATIN = (
    "A B V G D Đ E Ž Z I J K L Lj M N Nj O P R S T Ć U F H C Č Dž Š"
).split()
_TRANSLITERATION = dict(zip(_CYRILLIC, _LATIN, strict=True))
_TRANSLITERATION.update(
    {source.lower(): target.lower() for source, target in _TRANSLITERATION.items()}
)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_EKAVIAN = frozenset("mleko lepo vreme dete reka sneg svet čovek pesma".split())
_IJEKAVIAN = frozenset(
    "mlijeko lijepo vrijeme dijete rijeka snijeg svijet čovjek pjesma".split()
)
_NEIGHBOR = frozenset("tko uvjet tisuća zrakoplov veljača".split())


@dataclass(frozen=True, slots=True)
class NormalizedSerbian:
    original: str
    latin: str
    source_script: DetectedScript


@dataclass(frozen=True, slots=True)
class VariantReport:
    expected: SerbianVariant
    observed: SerbianVariant | None
    mixed: bool
    conforms: bool | None
    ekavian_score: int
    ijekavian_score: int
    neighbor_score: int


def normalize_serbian(text: str) -> NormalizedSerbian:
    original = unicodedata.normalize("NFC", text)
    script = detect_script(original, []).script
    latin = "".join(_TRANSLITERATION.get(character, character) for character in original)
    return NormalizedSerbian(original, latin, script)


def check_variant(text: str, lock: LanguageLock) -> VariantReport:
    if lock.language is not Language.SR or lock.variant is None:
        raise ValueError("variant checks require a Serbian language lock")
    words = set(_WORD.findall(normalize_serbian(text).latin.casefold()))
    ekavian = 2 * sum(word in _EKAVIAN for word in words)
    ijekavian = 2 * sum(word in _IJEKAVIAN for word in words)
    neighbor = sum(word in _NEIGHBOR for word in words)
    mixed = ekavian >= 2 and ijekavian >= 2
    observed = None
    if not mixed and max(ekavian, ijekavian) >= 4:
        observed = (
            SerbianVariant.EKAVIAN
            if ekavian > ijekavian
            else SerbianVariant.IJEKAVIAN
        )
    conforms = False if mixed else (observed is lock.variant if observed else None)
    return VariantReport(
        lock.variant, observed, mixed, conforms, ekavian, ijekavian, neighbor
    )
