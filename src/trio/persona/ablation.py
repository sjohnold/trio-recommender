"""Independent, reproducible Persona Engine ablation switches."""

from dataclasses import asdict, dataclass
from typing import Self


class AblationConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AblationConfig:
    stage1: bool = True
    stage2: bool = True
    stage3: bool = True
    baseline_prompt_only: bool = False

    def validate(self) -> Self:
        values = asdict(self)
        if any(type(value) is not bool for value in values.values()):
            raise AblationConfigError("ablation switches must be booleans")
        if self.baseline_prompt_only and any(
            (self.stage1, self.stage2, self.stage3)
        ):
            raise AblationConfigError(
                "prompt-only baseline requires stage1, stage2, and stage3 off"
            )
        return self

    def snapshot(self) -> dict[str, bool]:
        self.validate()
        return asdict(self)

