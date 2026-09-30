"""Mode-aware model routing without backend-specific dependencies."""

from dataclasses import dataclass, replace
from typing import Mapping

from trio.contracts import Language, Mode, Role
from trio.inference.residency import ResidencyReport

_CAPABILITIES = frozenset({"streaming", "cancel", "metrics"})
_LANGUAGES = frozenset(Language)


@dataclass(frozen=True, slots=True)
class ModelRef:
    name: str
    digest: str
    family: str
    memory_key: str | None = None
    capabilities: frozenset[str] = _CAPABILITIES
    languages: frozenset[Language] = _LANGUAGES

    def __post_init__(self) -> None:
        if not self.name or not self.digest or not self.family:
            raise ValueError("model name, digest, and family are required")
        if self.capabilities != _CAPABILITIES or self.languages != _LANGUAGES:
            raise ValueError("all routes require streaming/cancel/metrics and RU/EN/SR")


class ModelRouter:
    def __init__(
        self,
        mode_a: Mapping[Role, ModelRef],
        mode_b_actor: ModelRef,
        state: ModelRef,
        mode_a_residency: ResidencyReport,
    ) -> None:
        self.mode_a = {Role(role): ref for role, ref in mode_a.items()}
        self.mode_b_actor = mode_b_actor
        self.state = state
        self.mode_a_residency = mode_a_residency
        if set(self.mode_a) != set(Role):
            raise ValueError("Mode A requires one model per role")
        if state.name in {ref.name for ref in self.mode_a.values()} | {
            mode_b_actor.name
        }:
            raise ValueError("State Model must be separate from actor models")

    def resolve(self, mode: Mode | str, role: Role | str) -> ModelRef:
        selected_mode = Mode(getattr(mode, "value", mode))
        selected_role = Role(getattr(role, "value", role))
        if selected_mode is Mode.A:
            if not self.mode_a_residency.ready:
                raise RuntimeError(
                    f"Mode A residency failed: {self.mode_a_residency.reason}"
                )
            model = self.mode_a[selected_role]
        else:
            model = self.mode_b_actor
        return replace(model, memory_key=selected_role.value)

    def resolve_state(self) -> ModelRef:
        return self.state

    def snapshot(self, mode: Mode | str) -> dict:
        selected_mode = Mode(mode)
        actors = {
            role.value: self.resolve(selected_mode, role).digest for role in Role
        }
        return {
            "mode": selected_mode.value,
            "actor_digests": actors,
            "state_digest": self.state.digest,
        }
