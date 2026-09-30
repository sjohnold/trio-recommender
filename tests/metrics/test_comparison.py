import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.metrics.comparison import (
    DisagreementSample, RoleSample, agreement_threshold,
    disagreement_rate, persona_diversity,
)
from trio.metrics.features import FeatureVector
from trio.metrics.worldview import WorldviewObservation

def features(disagreement=0, causal=0):
    return FeatureVector(
        10, 4, 5, 0, 0, 0,
        {"disagreement": disagreement, "causal": causal}, 1, 0, 0,
    )

def sample(level, target=None, reason=False, disagreement=0, causal=0):
    worldview = WorldviewObservation(0, -1, .9, (), disagreement > 0, False)
    return DisagreementSample(
        "en", "counter", level, target, reason,
        features(disagreement, causal), worldview,
    )

def test_no_without_target_or_reason_is_not_substantive():
    samples = [
        sample(1, disagreement=10),
        sample(1, target="claim", disagreement=10),
        sample(1, target="claim", reason=True, disagreement=10),
    ]
    assert disagreement_rate(samples, "en", "counter") == 1 / 3
    assert disagreement_rate(samples, "ru", "counter") == 0

def test_threshold_is_computed_inside_language_and_scenario():
    samples = [sample(1, "claim", True, 10), sample(2)]
    samples.append(DisagreementSample(
        "ru", "counter", 2, "claim", True, features(10),
        WorldviewObservation(0, -1, .9, (), True, False),
    ))
    assert agreement_threshold(samples, "en", "counter") == 2


def test_pairwise_diversity_keeps_bootstrap_ready_samples():
    samples = [
        RoleSample("en", "pair", "r1", "a", {"x": 0, "y": 0}),
        RoleSample("en", "pair", "r1", "b", {"x": 3, "y": 4}),
        RoleSample("en", "pair", "r2", "a", {"x": 1, "y": 1}),
        RoleSample("en", "pair", "r2", "b", {"x": 1, "y": 1}),
        RoleSample("ru", "pair", "r1", "b", {"x": 99, "y": 99}),
    ]
    result = persona_diversity(samples, "en", "pair")
    assert result[0].roles == ("a", "b")
    assert result[0].samples == ((25 / 2) ** .5, 0)
    assert result[0].mean == (25 / 2) ** .5 / 2
