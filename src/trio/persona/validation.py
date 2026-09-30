"""Persona schema validation and one-way point budget."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from trio.contracts import Role

Stat = Annotated[StrictInt, Field(ge=1, le=10)]


class Alignment(StrEnum):
    LAWFUL_GOOD = "lawful_good"
    LAWFUL_NEUTRAL = "lawful_neutral"
    LAWFUL_EVIL = "lawful_evil"
    NEUTRAL_GOOD = "neutral_good"
    TRUE_NEUTRAL = "true_neutral"
    NEUTRAL_EVIL = "neutral_evil"
    CHAOTIC_GOOD = "chaotic_good"
    CHAOTIC_NEUTRAL = "chaotic_neutral"
    CHAOTIC_EVIL = "chaotic_evil"


class PersonaStats(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    energy: Stat
    openness: Stat
    nerve: Stat
    sharpness: Stat
    reasoning: Stat
    provocation: Stat
    attunement: Stat


class PersonaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=64)
    role: Role
    alignment: Alignment
    stats: PersonaStats

    @field_validator("name")
    @classmethod
    def require_visible_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must contain a visible character")
        return value


class PointBudgetError(ValueError):
    def __init__(self, used: int, available: int = 10) -> None:
        self.used = used
        self.available = available
        super().__init__(f"persona uses {used} bonus points; {available} available")


def validate_persona(data: dict) -> PersonaConfig:
    persona = PersonaConfig.model_validate(data)
    used = sum(max(value - 5, 0) for value in persona.stats.model_dump().values())
    if used > 10:
        raise PointBudgetError(used)
    return persona

