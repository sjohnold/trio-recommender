"""Deterministic, failure-isolated headless experiment runner."""
import asyncio
import random
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal
from trio.storage.sessions import SessionRepository
RunStatus = Literal["completed", "failed", "timed_out"]
Execute = Callable[[str, Mapping[str, Any], int], Awaitable[None]]
@dataclass(frozen=True, slots=True)
class RunnerSpec:
    document: Mapping[str, Any]
    sessions: SessionRepository
    execute: Execute
    hard_timeout: float
    def __post_init__(self) -> None:
        if self.hard_timeout <= 0:
            raise ValueError("hard_timeout must be positive")
@dataclass(frozen=True, slots=True)
class ExperimentRun:
    session_id: str | None
    repetition: int
    seed: int
    condition: Mapping[str, Any]
    status: RunStatus
    reason: str | None = None
@dataclass(frozen=True, slots=True)
class ExperimentRunSet:
    experiment_id: str
    runs: tuple[ExperimentRun, ...]
def _snapshot(document: Mapping[str, Any], condition, seed: int) -> dict:
    language = condition.get("language", document["language"])
    script = {"ru": "Cyrillic", "en": "Latin", "sr": "Latin"}[language]
    return {
        "mode": condition.get("mode", document["mode"]),
        "model_digests": document["model_digests"],
        "profile": document["profile"],
        "language_lock": {"language": language, "script": script},
        "ablations": condition.get("ablation", document["ablation"]),
        "personas": {"preset": condition["persona_preset"]},
        "experiment": {
            "id": document["id"], "seed": seed, "condition": condition,
        },
    }
async def _run_one(spec: RunnerSpec, repetition, seed, condition) -> ExperimentRun:
    session_id = None
    try:
        session_id = await spec.sessions.create_session(
            _snapshot(spec.document, condition, seed)
        )
        async with asyncio.timeout(spec.hard_timeout):
            await spec.execute(session_id, condition, seed)
        return ExperimentRun(session_id, repetition, seed, condition, "completed")
    except TimeoutError:
        return ExperimentRun(
            session_id, repetition, seed, condition, "timed_out", "hard_timeout"
        )
    except Exception as error:
        reason = f"{type(error).__name__}: {error}"
        return ExperimentRun(session_id, repetition, seed, condition, "failed", reason)
def _jobs(document):
    orders = document.get("counterbalance_orders")
    if orders:
        conditions = {item["condition_id"]: item for item in document["conditions"]}
        return [(r, document["seed"] + r, conditions[name])
                for r in range(document["repetitions"])
                for name in orders[r % len(orders)]]
    jobs = [
        (repetition, document["seed"] + repetition, condition)
        for repetition in range(document["repetitions"])
        for condition in document["conditions"]
    ]
    random.Random(document["seed"]).shuffle(jobs)
    return jobs
async def run_experiment(spec: RunnerSpec) -> ExperimentRunSet:
    runs = [await _run_one(spec, *job) for job in _jobs(spec.document)]
    document = spec.document
    return ExperimentRunSet(document["id"], tuple(runs))
