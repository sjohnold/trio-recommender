"""Mode-separated runtime latency and reliability aggregates."""
from dataclasses import dataclass
from statistics import fmean
from typing import Iterable, Mapping

from trio.inference.timing import LatencySample
from trio.orchestrator.events import UtteranceState


@dataclass(frozen=True, slots=True)
class RuntimeTargets:
    ttft_p95_ms: float; full_p95_ms: float; round_p95_ms: float
    max_timeout_rate: float; max_invalid_state_rate: float
@dataclass(frozen=True, slots=True)
class RuntimeSample:
    mode: str; latency: LatencySample; round_ms: float | None
    state: UtteranceState; reason: str | None; invalid_state: bool
    targets: RuntimeTargets
@dataclass(frozen=True, slots=True)
class Percentiles:
    p50: float | None; p95: float | None
@dataclass(frozen=True, slots=True)
class ModeRuntime:
    ttft: Percentiles; full: Percentiles; round: Percentiles
    timeout_rate: float | None; interruption_rate: float | None
    failure_rate: float | None; invalid_state_rate: float | None
    target_pass: Mapping[str, bool | None]
@dataclass(frozen=True, slots=True)
class RuntimeMetrics:
    by_mode: Mapping[str, ModeRuntime]
def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    low = int(position)
    fraction = position - low
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + fraction * (ordered[high] - ordered[low])
def _percentiles(values) -> Percentiles:
    values = [float(value) for value in values if value is not None]
    return Percentiles(_percentile(values, .5), _percentile(values, .95))
def _mode(samples: list[RuntimeSample]) -> ModeRuntime:
    ttft = _percentiles(item.latency.ttft_ms for item in samples)
    full = _percentiles(item.latency.total_ms for item in samples)
    rounds = _percentiles(item.round_ms for item in samples)
    if not samples:
        return ModeRuntime(
            ttft, full, rounds, None, None, None, None, dict.fromkeys(
                ("ttft", "full", "round", "reliability")
            ),
        )
    total = len(samples)
    timeout = fmean(item.state is UtteranceState.TIMED_OUT for item in samples)
    interrupted = fmean(item.state is UtteranceState.INTERRUPTED for item in samples)
    failure = fmean(item.state in {UtteranceState.FAILED, UtteranceState.TIMED_OUT}
                    or item.state is UtteranceState.INTERRUPTED
                    and item.reason != "user_interrupt" for item in samples)
    invalid = sum(item.invalid_state for item in samples) / total
    targets = samples[0].targets
    if any(item.targets != targets for item in samples):
        raise ValueError("runtime targets must be stable within a mode")
    passing = {
        "ttft": ttft.p95 <= targets.ttft_p95_ms if ttft.p95 is not None else None,
        "full": full.p95 <= targets.full_p95_ms if full.p95 is not None else None,
        "round": rounds.p95 <= targets.round_p95_ms if rounds.p95 is not None else None,
        "reliability": (
            timeout <= targets.max_timeout_rate
            and invalid <= targets.max_invalid_state_rate
        ),
    }
    return ModeRuntime(ttft, full, rounds, timeout, interrupted, failure, invalid, passing)
def aggregate_runtime(samples: Iterable[RuntimeSample]) -> RuntimeMetrics:
    grouped = {"A": [], "B": []}
    for sample in samples:
        if sample.mode not in grouped:
            raise ValueError(f"unsupported mode: {sample.mode}")
        grouped[sample.mode].append(sample)
    return RuntimeMetrics({mode: _mode(rows) for mode, rows in grouped.items()})
