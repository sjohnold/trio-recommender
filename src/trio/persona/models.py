"""Immutable persona-engine input separated from alignment policy."""

from pydantic import BaseModel, ConfigDict, Field

from trio.contracts import Role
from trio.persona.validation import Alignment as AlignmentPolicyKey
from trio.persona.validation import PersonaStats as ValidatedPersonaStats


class PersonaStats(ValidatedPersonaStats):
    def normalized(self, name: str) -> float:
        if name not in type(self).model_fields:
            raise KeyError(name)
        return (getattr(self, name) - 5.5) / 4.5


class PersonaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Role
    name: str = Field(min_length=1, max_length=64, pattern=r"\S")
    stats: PersonaStats
    alignment: AlignmentPolicyKey

