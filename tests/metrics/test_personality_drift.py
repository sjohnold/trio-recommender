import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.metrics.features import FeatureVector
from trio.metrics.personality_drift import (
    DriftState, DriftTarget, update_personality_drift,
)


def vector(value, words=20):
    return FeatureVector(
        words, value, value, value, 0, 0,
        {"causal": value}, 0, 0, 0,
    )


TARGET = DriftTarget(
    {"mean_word_length": 0, "words_per_sentence": 0,
     "punctuation_per_100": 0, "lexicon.causal": 0},
    {"mean_word_length": 1, "words_per_sentence": 1,
     "punctuation_per_100": 1, "lexicon.causal": 1},
    {"mean_word_length": "length", "words_per_sentence": "syntax",
     "punctuation_per_100": "punctuation", "lexicon.causal": "reasoning"},
    threshold=1,
)


def apply(values, state=DriftState()):
    observations = []
    for value in values:
        observation = update_personality_drift(state, vector(value), TARGET)
        state = observation.state
        observations.append(observation)
    return observations


def test_one_outlier_does_not_produce_drift():
    observations = apply([0, 0, 10, 0, 0, 0])
    assert not any(item.drift for item in observations)


def test_two_consecutive_rolling_windows_require_three_groups():
    observations = apply([2] * 6)
    assert observations[-2].drift is False
    assert observations[-1].drift is True
    assert len(observations[-1].deviated_groups) == 4


def test_short_and_interrupted_utterances_are_excluded():
    short = update_personality_drift(DriftState(), vector(9, words=2), TARGET)
    interrupted = update_personality_drift(
        DriftState(terminal_state="INTERRUPTED"), vector(9), TARGET
    )
    assert short.excluded == "too_short" and short.distance is None
    assert interrupted.excluded == "interrupted"
    assert short.state.history == interrupted.state.history == ()
