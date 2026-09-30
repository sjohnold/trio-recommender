"""Versioned feature calibration without cross-language pooling."""
from dataclasses import dataclass
from statistics import fmean, pstdev
from typing import Iterable, Mapping

from trio.metrics.features import FeatureVector
from trio.persona.models import PersonaStats

VERSION = "1.0.0"

class CalibrationMissingError(KeyError):
    pass


@dataclass(frozen=True, slots=True)
class CalibrationKey:
    language: str
    model_digest: str
    role: str

    def __post_init__(self) -> None:
        if not all((self.language, self.model_digest, self.role)):
            raise ValueError("calibration key fields are required")


@dataclass(frozen=True, slots=True)
class Distribution:
    mean: float
    sigma: float


@dataclass(frozen=True, slots=True)
class CalibrationSample:
    key: CalibrationKey
    vector: FeatureVector

def _values(vector: FeatureVector) -> dict[str, float]:
    values = {
        field: float(getattr(vector, field))
        for field in (
            "word_count", "mean_word_length", "words_per_sentence",
            "punctuation_per_100", "first_person_rate", "negation_rate",
            "mattr", "ngram_repetition", "reference_rate",
        )
    }
    values.update(
        {f"lexicon.{name}": float(value)
         for name, value in vector.lexicon_rates.items()}
    )
    return values


@dataclass(frozen=True, slots=True)
class Calibration:
    buckets: Mapping[CalibrationKey, Mapping[str, Distribution]]
    version: str = VERSION

    def _bucket(self, key: CalibrationKey) -> Mapping[str, Distribution]:
        try:
            return self.buckets[key]
        except KeyError as error:
            raise CalibrationMissingError(key) from error

    def zscore(
        self, vector: FeatureVector, key: CalibrationKey
    ) -> dict[str, float]:
        bucket = self._bucket(key)
        return {
            name: (value - bucket[name].mean) / (bucket[name].sigma or 1.0)
            for name, value in _values(vector).items()
        }

    def target(
        self, feature: str, key: CalibrationKey, stats: PersonaStats,
        stat: str, weight: float = 1.0,
    ) -> float:
        distribution = self._bucket(key)[feature]
        return distribution.mean + weight * stats.normalized(stat) * distribution.sigma


def fit_calibration(samples: Iterable[CalibrationSample]) -> Calibration:
    grouped: dict[CalibrationKey, list[dict[str, float]]] = {}
    for sample in samples:
        grouped.setdefault(sample.key, []).append(_values(sample.vector))
    if not grouped:
        raise ValueError("calibration requires samples")
    buckets = {}
    for key, rows in grouped.items():
        names = rows[0].keys()
        buckets[key] = {
            name: Distribution(fmean(row[name] for row in rows),
                               pstdev(row[name] for row in rows))
            for name in names
        }
    return Calibration(buckets)
