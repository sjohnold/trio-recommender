import asyncio
import sys
from pathlib import Path
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trio.diagnostics.memory import GIB, PROFILES, ProfileName
from trio.inference import residency
BASE = next(profile for profile in PROFILES if profile.name is ProfileName.BASE)
SPECS = (
    residency.ModelSpec("pragmatist", "qwen"),
    residency.ModelSpec("logician", "gemma"),
    residency.ModelSpec("empath", "llama"),
    residency.ModelSpec("state", "smollm", True),
)
def models(size=GIB):
    return [
        {
            "name": spec.name, "size": size, "size_vram": None,
            "details": {"family": spec.family},
        }
        for spec in SPECS
    ]
def test_preloads_four_distinct_families_and_admits(monkeypatch) -> None:
    preloaded = []
    async def preload(name, num_ctx):
        preloaded.append((name, num_ctx))
    async def loaded():
        return models()
    monkeypatch.setattr(residency, "_preload", preload)
    monkeypatch.setattr(residency, "_loaded", loaded)
    report = asyncio.run(residency.ensure_resident(SPECS, BASE))
    assert report.ready and report.reason == "admitted"
    assert preloaded == [(spec.name, BASE.num_ctx) for spec in SPECS]
    assert len(report.loaded_names) == 4


def test_eviction_or_overbudget_forbids_start(monkeypatch) -> None:
    async def preload(name, num_ctx):
        pass
    monkeypatch.setattr(residency, "_preload", preload)
    async def evicted():
        return models()[:-1]
    monkeypatch.setattr(residency, "_loaded", evicted)
    report = asyncio.run(residency.ensure_resident(SPECS, BASE))
    assert not report.ready and report.reason == "resident_set_mismatch"
    async def too_large():
        return models(2 * GIB)
    monkeypatch.setattr(residency, "_loaded", too_large)
    report = asyncio.run(residency.ensure_resident(SPECS, BASE))
    assert not report.ready and report.reason == "over_budget"


def test_duplicate_family_is_invalid_before_preload() -> None:
    duplicate = (
        SPECS[0],
        residency.ModelSpec("second", "qwen"),
        SPECS[2],
        SPECS[3],
    )
    report = asyncio.run(residency.ensure_resident(duplicate, BASE))
    assert not report.ready and report.reason == "invalid_mode_a_model_set"


def test_state_may_share_family_with_an_actor(monkeypatch) -> None:
    specs = (*SPECS[:3], residency.ModelSpec("state", "qwen", True))

    async def preload(name, num_ctx):
        pass

    async def loaded():
        return [
            {
                "name": spec.name, "size": GIB, "size_vram": None,
                "details": {"family": spec.family},
            }
            for spec in specs
        ]

    monkeypatch.setattr(residency, "_preload", preload)
    monkeypatch.setattr(residency, "_loaded", loaded)
    report = asyncio.run(residency.ensure_resident(specs, BASE))
    assert report.ready
