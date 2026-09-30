import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
from accept_mode_a import Model, Probe, accept_mode_a
MODELS = (
    Model("pragmatist", "family-p"), Model("logician", "family-l"),
    Model("empath", "family-e"), Model("state", "family-s", True),
)


class Backend:
    def __init__(self, size=1024 ** 3, evict=False, probes=None):
        self.size, self.evict, self.preloaded = size, evict, []
        self.probes = probes or [Probe(300, 1500, 4500, True)] * 3
        self.calls = 0
    async def preload(self, name, context):
        self.preloaded.append((name, context))
    async def ps(self):
        self.calls += 1
        models = MODELS[:-1] if self.evict and self.calls > 1 else MODELS
        return [{"name": model.name, "family": model.family, "size": self.size}
                for model in models]
    async def probe(self, actors):
        return self.probes


def run(backend, models=MODELS):
    return asyncio.run(accept_mode_a(models, backend))


def test_accepts_four_resident_models_and_base_targets():
    backend = Backend()
    result = run(backend)
    assert result.passed and result.reasons == ()
    assert backend.preloaded == [(model.name, 4096) for model in MODELS]
    assert result.resident == tuple(sorted(model.name for model in MODELS))


def test_refuses_before_probe_on_memory_or_invalid_families():
    backend = Backend(size=3 * 1024 ** 3)
    result = run(backend)
    assert result.reasons == ("memory_budget_exceeded",)
    assert backend.calls == 1
    duplicate = MODELS[:2] + (Model("empath", "family-p"), MODELS[3])
    assert run(Backend(), duplicate).reasons == ("invalid_mode_a_model_set",)


def test_eviction_latency_and_integrity_fail_explicitly():
    probes = [Probe(501, 2501, 6001, False)] * 3
    result = run(Backend(evict=True, probes=probes))
    assert set(result.reasons) == {
        "ttft_target_failed", "utterance_target_failed", "round_target_failed",
        "integrity_failed", "model_evicted",
    }
