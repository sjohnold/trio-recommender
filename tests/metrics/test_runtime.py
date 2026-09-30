import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.inference.timing import LatencySample
from trio.metrics.runtime import RuntimeSample, RuntimeTargets, aggregate_runtime
from trio.orchestrator.events import UtteranceState

TARGET = RuntimeTargets(200, 500, 700, .1, .1)
def sample(mode, ttft, full, round_ms, state, reason=None, invalid=False):
    return RuntimeSample(
        mode, LatencySample(ttft, full, None, None), round_ms,
        state, reason, invalid, TARGET,
    )
def test_empty_modes_return_null_not_zero():
    result = aggregate_runtime([]).by_mode
    assert result["A"].ttft.p50 is None
    assert result["A"].timeout_rate is None
    assert set(result["B"].target_pass.values()) == {None}
def test_percentiles_rates_and_user_interrupt():
    rows = [
        sample("A", 100, 300, 500, UtteranceState.COMPLETED),
        sample("A", 200, 500, 700, UtteranceState.INTERRUPTED, "user_interrupt"),
        sample("A", None, 700, None, UtteranceState.TIMED_OUT, "hard_timeout", True),
    ]
    result = aggregate_runtime(rows).by_mode["A"]
    assert result.ttft.p50 == 150 and result.ttft.p95 == 195
    assert result.full.p50 == 500 and result.round.p50 == 600
    assert result.timeout_rate == result.interruption_rate == 1 / 3
    assert result.failure_rate == 1 / 3
    assert result.invalid_state_rate == 1 / 3
    assert result.target_pass == {
        "ttft": True, "full": False, "round": True, "reliability": False,
    }
def test_targets_are_evaluated_separately_by_mode():
    strict = RuntimeTargets(50, 50, 50, 0, 0)
    mode_b = RuntimeSample(
        "B", LatencySample(100, 100, None, None), 100,
        UtteranceState.COMPLETED, None, False, strict,
    )
    result = aggregate_runtime([
        sample("A", 100, 300, 500, UtteranceState.COMPLETED), mode_b,
    ]).by_mode
    assert result["A"].target_pass["ttft"] is True
    assert result["B"].target_pass["ttft"] is False
