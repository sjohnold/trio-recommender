#!/usr/bin/env python3
"""Benchmark already-installed Ollama State Model candidates."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter
import httpx
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trio.settings import Settings
from trio.state.client import StateInferenceError, infer_state
from trio.state.prompt import build_state_prompt
from trio.state.validation import StateValidationError, validate_state
GIB = 1024**3
CASES = (
    ([{"speaker": "user", "text": "I agree; let us keep the plan."}],
     {"trend": "stable", "stance": "agree", "shift": False}),
    ([{"speaker": "user", "text": "No, that claim is wrong and this is getting worse."}],
     {"trend": "rising", "stance": "disagree", "shift": False}),
    ([{"speaker": "user", "text": "New question: when does the train leave?"}],
     {"trend": "unknown", "stance": "neutral", "shift": True}),
)
def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Benchmark installed 0.6–1.7B Ollama State Models; never downloads weights."
    )
    value.add_argument(
        "candidate", nargs="+", metavar="TAG=BILLIONS",
        help="installed Ollama tag and parameter size, for example model:latest=1.5",
    )
    value.add_argument("--timeout", type=float, default=10.0)
    value.add_argument("--max-latency", type=float, default=5.0)
    value.add_argument("--min-agreement", type=float, default=0.67)
    value.add_argument(
        "--output", type=Path, default=ROOT / "data/benchmarks/state_gate.json"
    )
    return value
def parse_candidates(values: list[str]) -> list[tuple[str, float]]:
    parsed = []
    for value in values:
        try:
            tag, size = value.rsplit("=", 1)
            billions = float(size)
        except ValueError as error:
            raise ValueError(f"invalid candidate {value!r}; use TAG=BILLIONS") from error
        if not tag or not 0.6 <= billions <= 1.7:
            raise ValueError(f"candidate {value!r} is outside 0.6–1.7B")
        parsed.append((tag, billions))
    return parsed
async def ollama_json(path: str) -> dict:
    url = f"{Settings.load().ollama_url}{path}"
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(url)
        response.raise_for_status()
        value = response.json()
    if not isinstance(value, dict):
        raise ValueError(f"{path} did not return a JSON object")
    return value


async def resident_bytes(tag: str) -> int | None:
    models = (await ollama_json("/api/ps")).get("models", [])
    for model in models:
        if model.get("name") == tag:
            return model.get("size_vram") or model.get("size")
    return None


async def benchmark(tag: str, billions: float, digest: str, args) -> dict:
    valid = agreements = 0
    latencies = []
    resident = None
    for events, expected in CASES:
        prompt = build_state_prompt(events, None, "en")
        started = perf_counter()
        try:
            state = validate_state(await infer_state(prompt, tag, args.timeout))
            valid += 1
            agreements += sum((
                state.trend == expected["trend"],
                state.user_signal["stance"] == expected["stance"],
                state.topic_shift["detected"] == expected["shift"],
            )) / 3
        except (StateInferenceError, StateValidationError, httpx.HTTPError):
            pass
        latencies.append(perf_counter() - started)
        resident = await resident_bytes(tag)
    count = len(CASES)
    result = {
        "tag": tag, "digest": digest, "billions": billions,
        "valid_json_rate": valid / count,
        "agreement": agreements / count,
        "mean_latency_seconds": sum(latencies) / count,
        "resident_bytes": resident,
    }
    result["passed"] = (
        result["valid_json_rate"] == 1
        and result["agreement"] >= args.min_agreement
        and result["mean_latency_seconds"] <= args.max_latency
        and resident is not None and resident <= GIB
    )
    return result


async def run(args) -> dict:
    candidates = parse_candidates(args.candidate)
    installed = {
        item["name"]: item for item in (await ollama_json("/api/tags")).get("models", [])
    }
    missing = [tag for tag, _ in candidates if tag not in installed]
    if missing:
        raise ValueError(f"models are not installed: {', '.join(missing)}")
    results = [
        await benchmark(tag, size, installed[tag].get("digest", ""), args)
        for tag, size in candidates
    ]
    if any(not item["digest"] for item in results):
        raise ValueError("Ollama did not provide a digest for every candidate")
    passing = [item for item in results if item["passed"]]
    passing.sort(key=lambda item: (
        -item["agreement"], item["mean_latency_seconds"],
        item["resident_bytes"], item["tag"],
    ))
    return {
        "version": 1,
        "thresholds": {
            "valid_json_rate": 1.0, "agreement": args.min_agreement,
            "max_latency_seconds": args.max_latency, "max_resident_bytes": GIB,
        },
        "winner": passing[0] if passing else None,
        "results": results,
    }


def main() -> None:
    args = parser().parse_args()
    report = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    if report["winner"] is None:
        raise SystemExit("no candidate passed the State Model gate")


if __name__ == "__main__":
    main()
