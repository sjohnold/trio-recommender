import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.metrics.calibration import (
    VERSION, CalibrationKey, CalibrationMissingError, CalibrationSample,
    fit_calibration,
)
from trio.metrics.features import FeatureVector

def vector(words):
    return FeatureVector(
        words, 4, words / 2, 10, 5, 2, {"causal": words}, 0.8, 0.1, 3
    )


def test_fit_keeps_language_digest_and_role_separate():
    en = CalibrationKey("en", "sha256:a", "logician")
    ru = CalibrationKey("ru", "sha256:a", "logician")
    calibration = fit_calibration([
        CalibrationSample(en, vector(10)), CalibrationSample(en, vector(20)),
        CalibrationSample(ru, vector(100)),
    ])
    assert calibration.version == VERSION
    assert calibration.buckets[en]["word_count"].mean == 15
    assert calibration.buckets[en]["word_count"].sigma == 5
    assert calibration.buckets[ru]["word_count"].mean == 100
    assert calibration.zscore(vector(20), en)["word_count"] == 1


def test_zero_sigma_and_digest_mismatch_are_explicit():
    key = CalibrationKey("en", "sha256:a", "empath")
    calibration = fit_calibration([CalibrationSample(key, vector(10))])
    assert calibration.zscore(vector(10), key)["word_count"] == 0
    foreign = CalibrationKey("en", "sha256:b", "empath")
    with pytest.raises(CalibrationMissingError):
        calibration.zscore(vector(10), foreign)


def test_stat_target_uses_normalized_persona_value():
    class Stats:
        def normalized(self, name):
            assert name == "energy"
            return 1.0
    key = CalibrationKey("en", "sha256:a", "pragmatist")
    calibration = fit_calibration([
        CalibrationSample(key, vector(10)), CalibrationSample(key, vector(20)),
    ])
    assert calibration.target("word_count", key, Stats(), "energy", 0.5) == 17.5
