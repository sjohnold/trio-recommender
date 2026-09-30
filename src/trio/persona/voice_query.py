"""Typed Stage 3 query and score contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from trio.contracts import Role
from trio.language.contracts import LanguageLock
from trio.persona.models import AlignmentPolicyKey, PersonaStats


class VoiceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    language: LanguageLock
    role: Role
    stats: PersonaStats
    alignment: AlignmentPolicyKey
    limit: Literal[2, 3] = 3

    def matches_hard_filters(self, language: LanguageLock, role: Role) -> bool:
        return self.language == language and self.role is role


class VoiceExampleScore(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    example_id: str = Field(min_length=1)
    distance: float = Field(ge=0)
    alignment_match: bool

