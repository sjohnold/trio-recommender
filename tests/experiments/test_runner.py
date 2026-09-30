import asyncio
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.experiments.runner import RunnerSpec, run_experiment
class Sessions:
    def __init__(self):
        self.snapshots = []
    async def create_session(self, snapshot):
        self.snapshots.append(snapshot)
        return f"session-{len(self.snapshots)}"
def document():
    return {
        "id": "experiment-1", "language": "sr", "seed": 17, "repetitions": 2,
        "mode": "A", "profile": "Base",
        "model_digests": {"state": "sha256:12345678", "actor": "sha256:87654321"},
        "ablation": {"stage1": True, "stage2": True, "stage3": True},
        "conditions": [
            {"name": "prompt_only", "provocation": 1, "persona_preset": "p",
             "ablation": {"stage1": False, "stage2": False, "stage3": False},
             "mode": "B", "language": "ru"},
            {"name": "persona_engine", "provocation": 5, "persona_preset": "p"},
            {"name": "language_comparison", "provocation": 9, "persona_preset": "p"},
        ],
    }
def execute(seen):
    async def run(session_id, condition, seed):
        seen.append((condition["name"], seed))
        if condition["name"] == "persona_engine":
            raise RuntimeError("isolated")
        if condition["name"] == "language_comparison":
            await asyncio.sleep(0.02)
    return run
def launch(timeout=0.005):
    sessions, seen = Sessions(), []
    spec = RunnerSpec(document(), sessions, execute(seen), timeout)
    return asyncio.run(run_experiment(spec)), sessions, seen
def test_order_is_deterministic_and_covers_repetitions_by_conditions():
    first, sessions, _ = launch()
    second, _, _ = launch()
    order = lambda result: [(run.repetition, run.seed, run.condition["name"])
                             for run in result.runs]
    assert order(first) == order(second)
    canonical = [(r, 17 + r, c["name"]) for r in range(2)
                 for c in document()["conditions"]]
    assert order(first) != canonical
    assert len(first.runs) == len(sessions.snapshots) == 6
    assert {(snap["mode"], snap["language_lock"]["language"]) for snap in
            sessions.snapshots} == {("A", "sr"), ("B", "ru")}
    assert {run.seed for run in first.runs} == {17, 18}
    assert len({run.session_id for run in first.runs}) == 6
def test_failure_and_timeout_are_explicit_without_losing_other_runs():
    result, _, seen = launch()
    assert [run.status for run in result.runs].count("completed") == 2
    assert [run.status for run in result.runs].count("failed") == 2
    assert [run.status for run in result.runs].count("timed_out") == 2
    assert len(seen) == len(result.runs) == 6
    assert {run.reason for run in result.runs if run.status == "timed_out"} == {
        "hard_timeout"
    }
def test_non_positive_hard_timeout_is_rejected():
    with pytest.raises(ValueError, match="hard_timeout"):
        RunnerSpec(document(), Sessions(), execute([]), 0)

def test_counterbalance_orders_are_applied_per_repetition():
    value = document()
    for name, item in zip(("a", "b", "c"), value["conditions"]):
        item["condition_id"] = name
    value["counterbalance_orders"] = [["a", "b", "c"], ["b", "c", "a"]]
    result = asyncio.run(run_experiment(RunnerSpec(value, Sessions(), execute([]), .1)))
    assert [run.condition["condition_id"] for run in result.runs] == ["a", "b", "c", "b", "c", "a"]
