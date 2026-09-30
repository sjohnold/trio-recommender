#!/usr/bin/env python3
"""Strict Mode A residency, latency, and integrity acceptance."""
import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from statistics import quantiles
BASE_BUDGET = 8 * 1024 ** 3
@dataclass(frozen=True, slots=True)
class Model:
    name: str
    family: str
    state: bool = False
@dataclass(frozen=True, slots=True)
class Probe:
    ttft_ms: float
    utterance_ms: float
    round_ms: float
    integrity: bool
@dataclass(frozen=True, slots=True)
class Acceptance:
    passed: bool
    reasons: tuple[str, ...]
    resident: tuple[str, ...]
    required_bytes: int
def _p95(values):
    values = list(values)
    return values[0] if len(values) == 1 else quantiles(values, n=20)[18]


def _resident(snapshot):
    return {
        item.get("name", item.get("model")): item for item in snapshot
        if item.get("name", item.get("model"))
    }


async def accept_mode_a(models, backend, budget_bytes=BASE_BUDGET) -> Acceptance:
    models = tuple(models)
    actors, states = [m for m in models if not m.state], [m for m in models if m.state]
    if (len(actors), len(states), len({m.name for m in models}),
            len({m.family for m in models})) != (3, 1, 4, 4):
        return Acceptance(False, ("invalid_mode_a_model_set",), (), 0)
    for model in models:
        await backend.preload(model.name, 4096)
    before = _resident(await backend.ps())
    names = {model.name for model in models}
    required = sum(item.get("size", 0) for item in before.values())
    reasons = []
    if set(before) != names:
        reasons.append("resident_set_mismatch")
    if any(before.get(model.name, {}).get("family") != model.family for model in models):
        reasons.append("family_mismatch")
    if required > budget_bytes:
        reasons.append("memory_budget_exceeded")
    if reasons:
        return Acceptance(False, tuple(reasons), tuple(sorted(before)), required)
    probes = tuple(await backend.probe(tuple(model.name for model in actors)))
    if not probes:
        reasons.append("insufficient_probes")
    else:
        if _p95(p.ttft_ms for p in probes) > 500:
            reasons.append("ttft_target_failed")
        if _p95(p.utterance_ms for p in probes) > 2500:
            reasons.append("utterance_target_failed")
        if _p95(p.round_ms for p in probes) > 6000:
            reasons.append("round_target_failed")
        if not all(p.integrity for p in probes):
            reasons.append("integrity_failed")
    after = _resident(await backend.ps())
    if set(after) != names or any(
        after[name].get("size") != before[name].get("size") for name in names
    ):
        reasons.append("model_evicted")
    return Acceptance(not reasons, tuple(reasons), tuple(sorted(after)), required)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", help="Python module exposing models and backend fixture")
    args = parser.parse_args()
    module = __import__(args.evidence, fromlist=("models", "backend"))
    result = asyncio.run(accept_mode_a(module.models, module.backend))
    print(json.dumps(asdict(result), ensure_ascii=False))
    raise SystemExit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
