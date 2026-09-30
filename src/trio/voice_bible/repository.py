"""Validated, deterministic JSONL repository for voice examples."""
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from trio.contracts import Role
from trio.language.contracts import LanguageLock
from trio.persona.models import PersonaStats
from trio.persona.selector import select_examples
from trio.persona.voice_query import VoiceQuery
_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_ALIGNMENTS = {
    "lawful_good", "lawful_neutral", "lawful_evil",
    "neutral_good", "true_neutral", "neutral_evil",
    "chaotic_good", "chaotic_neutral", "chaotic_evil",
}
_FIELDS = {
    "id", "language", "role", "stats", "alignment", "topic", "text",
    "source_kind", "review_status", "real_person_based", "machine_translated",
}
class VoiceBibleValidationError(ValueError):
    """A row failed validation; the message includes its source line."""
def _fingerprint(text: str) -> str:
    normalized = " ".join(text.casefold().split()).encode()
    return hashlib.sha256(normalized).hexdigest()
@dataclass(frozen=True, slots=True)
class VoiceExample:
    id: str
    language: LanguageLock
    role: Role
    stats: PersonaStats
    alignment: str
    topic: str
    text: str
    source_kind: str
    review_status: str
    fingerprint: str
@dataclass(frozen=True, slots=True)
class VoiceBible:
    examples: tuple[VoiceExample, ...]

    @classmethod
    def load(cls, path: str | Path) -> "VoiceBible":
        root = Path(path)
        files = sorted(root.glob("*.jsonl")) if root.is_dir() else [root]
        if not files or any(not file.is_file() for file in files):
            raise VoiceBibleValidationError(f"no JSONL files at {root}")
        examples: list[VoiceExample] = []
        fingerprints: dict[str, str] = {}
        for file in files:
            for number, line in enumerate(file.read_text().splitlines(), 1):
                try:
                    raw = json.loads(line)
                    example = _parse(raw)
                    previous = fingerprints.get(example.fingerprint)
                    if previous:
                        raise ValueError(f"duplicate text; first seen at {previous}")
                    fingerprints[example.fingerprint] = f"{file}:{number}"
                    examples.append(example)
                except (json.JSONDecodeError, TypeError, ValueError) as error:
                    raise VoiceBibleValidationError(
                        f"{file}:{number}: {error}"
                    ) from error
        return cls(tuple(examples))

    def query(self, query: VoiceQuery) -> list[VoiceExample]:
        approved = [
            item for item in self.examples if item.review_status == "approved"
        ]
        return select_examples(query, approved)
def _parse(raw: object) -> VoiceExample:
    if not isinstance(raw, dict) or set(raw) != _FIELDS:
        raise ValueError("row fields do not match schema")
    text = raw["text"]
    topic = raw["topic"]
    if not isinstance(text, str) or not 20 <= len(text.split()) <= 120:
        raise ValueError("text must contain 20..120 words")
    if not isinstance(topic, str) or not 1 <= len(topic) <= 48:
        raise ValueError("topic must contain 1..48 characters")
    if not isinstance(raw["id"], str) or not _ID.fullmatch(raw["id"]):
        raise ValueError("invalid id")
    if raw["alignment"] not in _ALIGNMENTS:
        raise ValueError("invalid alignment")
    if raw["source_kind"] not in {"authored", "pilot"}:
        raise ValueError("invalid source_kind")
    if raw["review_status"] not in {"draft", "reviewed", "approved", "rejected"}:
        raise ValueError("invalid review_status")
    if raw["real_person_based"] is not False or raw["machine_translated"] is not False:
        raise ValueError("prohibited provenance")
    return VoiceExample(
        raw["id"], LanguageLock(**raw["language"]), Role(raw["role"]),
        PersonaStats(**raw["stats"]), raw["alignment"], topic, text,
        raw["source_kind"], raw["review_status"], _fingerprint(text),
    )
