"""Deterministic, language-local speech feature extraction."""
from dataclasses import dataclass
from typing import Mapping, Sequence

from trio.metrics.tokenize import TokenDocument

_LEXICONS = {
    "hedge": ("might", "could be", "i think", "i suspect", "in my view", "кажется", "вероятно", "možda", "čini se"),
    "disagreement": ("i disagree", "that is incorrect", "that does not follow", "не согласен", "это неверно", "ne slažem se", "to nije tačno"),
    "softener": ("well", "i see the point but", "i am not sure that", "не уверен что", "частично согласен однако", "razumem poentu ali"),
    "intensifier": ("clearly", "definitely", "absolutely", "явно", "безусловно", "jasno", "kategorički"),
    "causal": ("because", "therefore", "the reason is", "потому что", "следовательно", "zato što", "dakle"),
    "analogy": ("this is like", "imagine", "by analogy", "это как", "представим", "to je kao", "zamislimo"),
    "affiliation": ("fair point", "i understand", "your argument", "понимаю", "важный момент", "razumem", "dobro zapažanje"),
}
_FIRST = frozenset("i me my mine we us our ours я меня мне мой моя мы нас наш ja mene mi moj moja naš".split())
_NEGATION = frozenset("no not never neither don't isn't не нет ни ne nije nema".split())
_REFERENCES = frozenset("you your yours ты тебе тебя твой вы вам вас ваш ti tebi tvoj vi vam vaš".split())
_PUNCTUATION = frozenset("!?.,;:…—")


@dataclass(frozen=True, slots=True)
class FeatureVector:
    word_count: int
    mean_word_length: float
    words_per_sentence: float
    punctuation_per_100: float
    first_person_rate: float
    negation_rate: float
    lexicon_rates: Mapping[str, float]
    mattr: float
    ngram_repetition: float
    reference_rate: float


def _rate(count: float, total: int) -> float:
    return count * 100 / total if total else 0.0


def _mattr(tokens: tuple[str, ...], window: int = 50) -> float:
    if not tokens:
        return 0.0
    size = min(window, len(tokens))
    windows = [tokens[index:index + size] for index in range(len(tokens) - size + 1)]
    return sum(len(set(part)) / size for part in windows) / len(windows)


def _repetition(
    tokens: tuple[str, ...], previous: Sequence[TokenDocument]
) -> float:
    scores = []
    for document in previous[-2:]:
        for size in range(2, 5):
            current = [tokens[i:i + size] for i in range(len(tokens) - size + 1)]
            earlier = {
                document.lemmas[i:i + size]
                for i in range(len(document.lemmas) - size + 1)
            }
            if current:
                scores.append(sum(gram in earlier for gram in current) / len(current))
    return max(scores, default=0.0)


def extract_features(
    doc: TokenDocument, previous_docs: Sequence[TokenDocument]
) -> FeatureVector:
    tokens = doc.lemmas
    count = len(tokens)
    text = " ".join(tokens)
    padded = f" {text} "
    rates = {
        category: _rate(sum(padded.count(f" {pattern} ") for pattern in patterns), count)
        for category, patterns in _LEXICONS.items()
    }
    return FeatureVector(
        count,
        sum(map(len, tokens)) / count if count else 0.0,
        count / len(doc.sentences) if doc.sentences else 0.0,
        _rate(sum(char in _PUNCTUATION for char in doc.original), count),
        _rate(sum(token in _FIRST for token in tokens), count),
        _rate(sum(token in _NEGATION for token in tokens), count),
        rates,
        _mattr(tokens),
        _repetition(tokens, previous_docs),
        _rate(sum(token in _REFERENCES for token in tokens), count),
    )
