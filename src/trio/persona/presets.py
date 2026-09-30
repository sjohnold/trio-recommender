"""Versioned JSON preset repository with atomic writes."""

import json
import os
import tempfile
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from trio.persona.models import PersonaConfig
from trio.persona.validation import validate_persona

VERSION = "1.0.0"


class PresetVersionError(ValueError):
    def __init__(self, found: object) -> None:
        self.found = found
        self.supported = VERSION
        super().__init__(f"unsupported preset version {found!r}; expected {VERSION}")


class TrioPreset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1.0.0"] = VERSION
    personas: tuple[PersonaConfig, PersonaConfig, PersonaConfig]

    @model_validator(mode="after")
    def validate_personas(self) -> Self:
        roles = {persona.role for persona in self.personas}
        if len(roles) != 3:
            raise ValueError("preset must contain three unique roles")
        for persona in self.personas:
            validate_persona(persona.model_dump())
        return self


def _safe_path(path: str | Path) -> Path:
    candidate = Path(path)
    if ".." in candidate.parts:
        raise ValueError("path traversal is not allowed")
    if candidate.suffix.lower() != ".json":
        raise ValueError("preset path must end in .json")
    return candidate.resolve()


def load_preset(path: str | Path) -> TrioPreset:
    data = json.loads(_safe_path(path).read_text(encoding="utf-8"))
    if data.get("version") != VERSION:
        raise PresetVersionError(data.get("version"))
    return TrioPreset.model_validate(data)


def save_preset(preset: TrioPreset, path: str | Path) -> None:
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(preset.model_dump(mode="json"), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

