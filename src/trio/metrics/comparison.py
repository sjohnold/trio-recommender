"""Within-scenario disagreement and standardized persona diversity."""
from dataclasses import dataclass
from itertools import combinations
from math import sqrt
from statistics import fmean
from typing import Iterable, Mapping

from trio.metrics.features import FeatureVector
from trio.metrics.worldview import WorldviewObservation

@dataclass(frozen=True, slots=True)
class DisagreementSample:
    language: str
    scenario: str
    provocation: int
    target: str | None
    has_reason: bool
    features: FeatureVector
    worldview: WorldviewObservation

    def substantive(self) -> bool:
        disagreement = self.features.lexicon_rates.get("disagreement", 0) > 0
        causal = self.features.lexicon_rates.get("causal", 0) > 0
        return bool(
            self.target and (self.has_reason or causal)
            and (disagreement or self.worldview.argument_attack)
        )

@dataclass(frozen=True, slots=True)
class RoleSample:
    language: str
    scenario: str
    replicate: str
    role: str
    standardized: Mapping[str, float]

@dataclass(frozen=True, slots=True)
class PairwiseDiversity:
    roles: tuple[str, str]
    mean: float
    samples: tuple[float, ...]

def _within(samples, language, scenario):
    return [
        sample for sample in samples
        if sample.language == language and sample.scenario == scenario
    ]

def disagreement_rate(
    samples: Iterable[DisagreementSample], language: str, scenario: str,
    provocation: int | None = None,
) -> float:
    selected = _within(samples, language, scenario)
    if provocation is not None:
        selected = [item for item in selected if item.provocation == provocation]
    return fmean(item.substantive() for item in selected) if selected else 0.0

def agreement_threshold(
    samples: Iterable[DisagreementSample], language: str, scenario: str,
    threshold: float = 0.2,
) -> int | None:
    selected = _within(samples, language, scenario)
    levels = sorted({item.provocation for item in selected})
    return next(
        (level for level in levels
         if disagreement_rate(selected, language, scenario, level) < threshold),
        None,
    )

def _distance(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    if set(left) != set(right) or not left:
        raise ValueError("standardized vectors require equal non-empty features")
    return sqrt(fmean((left[name] - right[name]) ** 2 for name in left))

def persona_diversity(
    samples: Iterable[RoleSample], language: str, scenario: str,
) -> tuple[PairwiseDiversity, ...]:
    selected = _within(samples, language, scenario)
    roles = sorted({sample.role for sample in selected})
    result = []
    for left, right in combinations(roles, 2):
        by_run = {}
        for item in selected:
            by_run.setdefault(item.replicate, {})[item.role] = item.standardized
        distances = tuple(
            _distance(run[left], run[right]) for run in by_run.values()
            if left in run and right in run
        )
        if distances:
            result.append(PairwiseDiversity((left, right), fmean(distances), distances))
    return tuple(result)
