import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.metrics.features import FeatureVector
from trio.metrics.worldview import observe_worldview


def features(affiliation=0, references=0):
    return FeatureVector(
        20, 4, 10, 5, 0, 0, {"affiliation": affiliation},
        0.8, 0, references,
    )


def test_order_and_support_use_queue_relevance_target_and_features():
    observation = observe_worldview(
        {"id": "u", "target": "user"},
        [
            {"utterance_id": "u", "kind": "queue", "respected": True},
            {"utterance_id": "u", "kind": "relevance", "value": 0.8},
            {"utterance_id": "u", "kind": "support"},
        ],
        features(affiliation=5, references=5),
    )
    assert observation.observed_order == 0.9
    assert observation.observed_communion > 0
    assert observation.confidence > 0.65


def test_argument_attack_is_distinct_from_personal_attack():
    argument = observe_worldview(
        {"id": "u"}, [{"kind": "argument_attack"}], features()
    )
    personal = observe_worldview(
        {"id": "u"}, [{"kind": "personal_attack"}], features()
    )
    assert argument.argument_attack and not argument.personal_attack
    assert personal.personal_attack and not personal.argument_attack
    assert argument.evidence != personal.evidence


def test_low_evidence_has_low_confidence_and_neutral_unknown_axis():
    observation = observe_worldview(
        {"id": "u", "target": "logician"}, [], features()
    )
    assert observation.confidence < 0.65
    assert observation.observed_order == observation.observed_communion == 0


def test_unrelated_events_are_ignored():
    observation = observe_worldview(
        {"id": "u"}, [{"utterance_id": "other", "kind": "support"}], features()
    )
    assert observation.evidence == ()
    assert observation.confidence == 0.25
