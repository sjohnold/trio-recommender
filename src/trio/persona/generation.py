"""Deterministic Stage 1 mapping from persona stats to inference options."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from trio.persona.models import PersonaStats

_MAP_PATH = Path(__file__).parents[3] / "data/persona/generation_map.json"
_MAP = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
if _MAP.get("version") != "1.0.0":
    raise ValueError("unsupported generation map version")


class ContextProfile(Protocol):
    num_ctx: int


@dataclass(frozen=True, slots=True)
class InferenceOptions:
    temperature: float
    min_p: float
    repeat_penalty: float
    num_predict: int
    num_ctx: int


def _mapped(rule: dict, stats: PersonaStats, enabled: bool) -> float:
    value = float(rule["base"])
    if enabled:
        value += sum(
            coefficient * stats.normalized(name)
            for name, coefficient in rule["contributions"].items()
        )
    return min(float(rule["max"]), max(float(rule["min"]), value))


def map_generation(
    stats: PersonaStats, profile: ContextProfile, enabled: bool = True
) -> InferenceOptions:
    rules = _MAP["parameters"]
    return InferenceOptions(
        temperature=round(_mapped(rules["temperature"], stats, enabled), 4),
        min_p=round(_mapped(rules["min_p"], stats, enabled), 4),
        repeat_penalty=round(
            _mapped(rules["repeat_penalty"], stats, enabled), 4
        ),
        num_predict=round(_mapped(rules["num_predict"], stats, enabled)),
        num_ctx=profile.num_ctx,
    )

