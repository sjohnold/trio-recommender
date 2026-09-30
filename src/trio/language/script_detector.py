"""Unicode script detection with explicit exclusion spans."""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

_AUTO_IGNORED = re.compile(
    r"https?://\S+|www\.\S+|```.*?```|`[^`\n]*`|^>[^\n]*",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("span must satisfy 0 <= start <= end")


class DetectedScript(StrEnum):
    LATIN = "Latn"
    CYRILLIC = "Cyrl"
    MIXED = "Mixed"
    UNKNOWN = "Unknown"


@dataclass(frozen=True, slots=True)
class ScriptReport:
    script: DetectedScript
    latin_letters: int
    cyrillic_letters: int
    ignored_characters: int


def _script_of(character: str) -> DetectedScript | None:
    name = unicodedata.name(character, "")
    if "LATIN" in name and unicodedata.category(character).startswith("L"):
        return DetectedScript.LATIN
    if "CYRILLIC" in name and unicodedata.category(character).startswith("L"):
        return DetectedScript.CYRILLIC
    return None


def detect_script(text: str, ignored_spans: list[Span]) -> ScriptReport:
    ignored = bytearray(len(text))
    spans = [*ignored_spans, *(Span(match.start(), match.end()) for match in _AUTO_IGNORED.finditer(text))]
    for span in spans:
        if span.end > len(text):
            raise ValueError("ignored span exceeds text")
        ignored[span.start : span.end] = b"\x01" * (span.end - span.start)
    latin = cyrillic = 0
    for index, character in enumerate(text):
        if ignored[index]:
            continue
        script = _script_of(character)
        latin += script is DetectedScript.LATIN
        cyrillic += script is DetectedScript.CYRILLIC
    if latin and cyrillic:
        detected = DetectedScript.MIXED
    elif latin:
        detected = DetectedScript.LATIN
    elif cyrillic:
        detected = DetectedScript.CYRILLIC
    else:
        detected = DetectedScript.UNKNOWN
    return ScriptReport(detected, latin, cyrillic, sum(bool(value) for value in ignored))
