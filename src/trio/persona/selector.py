"""Stable, diverse Stage 3 voice-example selection."""

import warnings
from dataclasses import dataclass
from typing import Protocol

from trio.contracts import Role
from trio.language.contracts import LanguageLock
from trio.persona.distance import ScoredVoiceExample, score_example
from trio.persona.voice_query import VoiceQuery


class VoiceExample(ScoredVoiceExample, Protocol):
    id: str
    text: str
    topic: str
    language: LanguageLock
    role: Role


class InsufficientVoiceExamplesWarning(UserWarning):
    pass


@dataclass(frozen=True, slots=True)
class RankedVoiceExample:
    """Explainable candidate score returned by the recommendation API."""

    example: VoiceExample
    rank: int
    distance: float
    alignment_match: bool
    selected: bool
    diversity_topic: str


def _normalized_text(text: str) -> str:
    return " ".join(text.casefold().split())


def select_examples(
    query: VoiceQuery, candidates: list[VoiceExample]
) -> list[VoiceExample]:
    eligible = [
        candidate
        for candidate in candidates
        if query.matches_hard_filters(candidate.language, candidate.role)
    ]
    ranked = sorted(eligible, key=lambda item: (score_example(query, item), item.id))
    selected: list[VoiceExample] = []
    texts: set[str] = set()
    topics: set[str] = set()
    for require_new_topic in (True, False):
        for candidate in ranked:
            text = _normalized_text(candidate.text)
            if candidate in selected or text in texts:
                continue
            if require_new_topic and candidate.topic in topics:
                continue
            selected.append(candidate)
            texts.add(text)
            topics.add(candidate.topic)
            if len(selected) == query.limit:
                return selected
    warnings.warn(
        f"only {len(selected)} of {query.limit} voice examples are available",
        InsufficientVoiceExamplesWarning,
        stacklevel=2,
    )
    return selected


def rank_examples(
    query: VoiceQuery, candidates: list[VoiceExample]
) -> list[RankedVoiceExample]:
    """Return the full eligible ranking plus the final diversified decision.

    This separates candidate generation, scoring and re-ranking so evaluation and
    API consumers can inspect why an example was or was not selected.
    """
    eligible = [
        candidate for candidate in candidates
        if query.matches_hard_filters(candidate.language, candidate.role)
    ]
    ordered = sorted(eligible, key=lambda item: (score_example(query, item), item.id))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsufficientVoiceExamplesWarning)
        selected_ids = {item.id for item in select_examples(query, candidates)}
    return [
        RankedVoiceExample(
            example=item,
            rank=index,
            distance=score_example(query, item),
            alignment_match=item.alignment is query.alignment,
            selected=item.id in selected_ids,
            diversity_topic=item.topic,
        )
        for index, item in enumerate(ordered, 1)
    ]
