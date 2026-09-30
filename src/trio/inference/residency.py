"""Preload and strict residency admission for Mode A."""
from dataclasses import dataclass
from typing import Iterable
import httpx
from trio.diagnostics.memory import Profile, ResidentModel, admit
from trio.settings import Settings
@dataclass(frozen=True, slots=True)
class ModelSpec:
    name: str
    family: str
    is_state: bool = False
@dataclass(frozen=True, slots=True)
class ResidencyReport:
    ready: bool
    reason: str
    loaded_names: tuple[str, ...]
    required_bytes: int
    budget_bytes: int
async def _preload(model: str, num_ctx: int) -> None:
    payload = {
        "model": model, "prompt": "", "stream": False, "keep_alive": -1,
        "options": {"num_ctx": num_ctx, "num_predict": 0},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{Settings.load().ollama_url}/api/generate", json=payload
        )
        response.raise_for_status()
async def _loaded() -> list[dict]:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(f"{Settings.load().ollama_url}/api/ps")
        response.raise_for_status()
        value = response.json()
    if not isinstance(value, dict) or not isinstance(value.get("models"), list):
        raise ValueError("Ollama /api/ps returned an invalid response")
    return value["models"]


async def ensure_resident(
    model_set: Iterable[ModelSpec], profile: Profile
) -> ResidencyReport:
    specs = tuple(model_set)
    names = {spec.name for spec in specs}
    actors = tuple(spec for spec in specs if not spec.is_state)
    actor_families = {spec.family for spec in actors}
    if (
        len(specs) != 4
        or len(names) != 4
        or len(actors) != 3
        or len(actor_families) != 3
        or sum(spec.is_state for spec in specs) != 1
    ):
        return ResidencyReport(
            False, "invalid_mode_a_model_set", (), 0, profile.budget_bytes
        )
    for spec in specs:
        await _preload(spec.name, profile.num_ctx)
    loaded = await _loaded()
    loaded_by_name = {
        item.get("name", item.get("model")): item for item in loaded
    }
    loaded_names = tuple(sorted(name for name in loaded_by_name if name))
    if set(loaded_by_name) != names:
        return ResidencyReport(
            False, "resident_set_mismatch", loaded_names, 0, profile.budget_bytes
        )
    expected = {spec.name: spec for spec in specs}
    if any(
        item.get("details", {}).get("family") != expected[name].family
        for name, item in loaded_by_name.items()
    ):
        return ResidencyReport(
            False, "family_mismatch", loaded_names, 0, profile.budget_bytes
        )
    resident = [
        ResidentModel(
            name,
            item.get("size"),
            item.get("size_vram"),
            expected[name].is_state,
        )
        for name, item in loaded_by_name.items()
    ]
    admission = admit(resident, profile)
    return ResidencyReport(
        admission.admitted,
        admission.reason.value,
        loaded_names,
        admission.required_bytes,
        admission.budget_bytes,
    )
