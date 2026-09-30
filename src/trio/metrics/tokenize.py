"""Small deterministic tokenizer shared by RU, EN, and SR metrics."""
import re
from dataclasses import dataclass

from trio.language.contracts import LanguageLock
from trio.language.serbian import normalize_serbian

_TOKEN = re.compile(
    r"\d+(?:[.,]\d+)*|(?:[^\W\d_]\.){2,}|"
    r"[^\W\d_]+(?:[-’'][^\W\d_]+)*",
    re.UNICODE,
)
_ABBREVIATIONS = re.compile(
    r"\b(?:dr|mr|mrs|ms|prof|г|ул|им|т\.е|т\.д|npr|tj)\.",
    re.IGNORECASE,
)
_CYRILLIC = re.compile(r"[\u0400-\u052f]")
_LATIN = re.compile(r"[A-Za-z\u00c0-\u024f]")


@dataclass(frozen=True, slots=True)
class ScriptSpan:
    start: int
    end: int
    script: str
    text: str


@dataclass(frozen=True, slots=True)
class TokenDocument:
    original: str
    tokens: tuple[str, ...]
    lemmas: tuple[str, ...]
    sentences: tuple[str, ...]
    script_spans: tuple[ScriptSpan, ...]
    sr_canonical: str | None


def _sentences(text: str) -> tuple[str, ...]:
    protected = _ABBREVIATIONS.sub(
        lambda match: match.group().replace(".", "\uff0e"), text
    )
    parts = re.split(r"(?<=[.!?])(?:[\"”»)]*)\s+", protected.strip())
    return tuple(
        part.replace("\uff0e", ".").strip() for part in parts if part.strip()
    )


def _spans(text: str) -> tuple[ScriptSpan, ...]:
    spans = []
    for match in _TOKEN.finditer(text):
        token = match.group()
        scripts = {
            "Cyrl" if _CYRILLIC.search(char) else "Latn"
            for char in token
            if _CYRILLIC.search(char) or _LATIN.search(char)
        }
        if scripts:
            script = scripts.pop() if len(scripts) == 1 else "Mixed"
            spans.append(ScriptSpan(match.start(), match.end(), script, token))
    return tuple(spans)


def tokenize(text: str, language_lock: LanguageLock) -> TokenDocument:
    original = text
    language = getattr(language_lock.language, "value", language_lock.language)
    canonical = normalize_serbian(original).latin if language == "sr" else None
    tokens = tuple(match.group() for match in _TOKEN.finditer(original))
    lemma_text = canonical if canonical is not None else original
    lemmas = tuple(
        match.group().casefold().replace("’", "'")
        for match in _TOKEN.finditer(lemma_text)
    )
    return TokenDocument(
        original, tokens, lemmas, _sentences(original), _spans(original), canonical
    )
