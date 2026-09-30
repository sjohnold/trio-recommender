import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.metrics.worldview import WorldviewObservation
from trio.metrics.worldview_drift import update_worldview_drift


def observation(order, communion, confidence=0.9):
    return WorldviewObservation(
        order, communion, confidence, (), False, False
    )


def test_two_confident_windows_are_required():
    history = [observation(-1, 1)] * 6
    first = update_worldview_drift(history[:5], "lawful_good")
    second = update_worldview_drift(history, "lawful_good")
    assert first.drift is False and first.previous_cell is None
    assert second.drift is True
    assert second.observed_cell == second.previous_cell == "chaotic_good"
    assert second.order_band == -1 and second.communion_band == 1


def test_low_confidence_latest_observation_is_excluded():
    history = [observation(-1, -1)] * 6
    history.append(observation(-1, -1, confidence=0.64))
    result = update_worldview_drift(history, "lawful_good")
    assert result.excluded and not result.drift
    assert result.confidence == 0.64


def test_one_outlier_does_not_change_two_windows():
    history = [observation(1, 1)] * 5
    history.insert(2, observation(-1, -1))
    result = update_worldview_drift(history, "lawful_good")
    assert result.observed_cell == "lawful_good"
    assert result.drift is False


def test_neutral_thresholds_keep_axes_separate():
    history = [observation(0.33, -0.33)] * 5
    result = update_worldview_drift(history, "true_neutral")
    assert result.order_band == result.communion_band == 0
    assert result.observed_cell == "true_neutral"
