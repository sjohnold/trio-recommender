"""Validated language, script, and Serbian-variant contracts."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator

from trio.contracts import Language


class Script(StrEnum):
    LATIN = "Latn"
    CYRILLIC = "Cyrl"


class SerbianVariant(StrEnum):
    EKAVIAN = "ekavian"
    IJEKAVIAN = "ijekavian"


class LanguageLock(BaseModel):
    model_config = {"frozen": True}

    language: Language
    script: Script | None = None
    variant: SerbianVariant | None = None

    @model_validator(mode="after")
    def validate_combination(self) -> Self:
        if self.language is Language.SR:
            object.__setattr__(self, "script", self.script or Script.LATIN)
            object.__setattr__(
                self, "variant", self.variant or SerbianVariant.EKAVIAN
            )
            return self
        expected = Script.CYRILLIC if self.language is Language.RU else Script.LATIN
        object.__setattr__(self, "script", self.script or expected)
        if self.script is not expected:
            raise ValueError(f"{self.language} requires {expected} script")
        if self.variant is not None:
            raise ValueError("variant is only valid for Serbian")
        return self


class LanguageCheckResult(BaseModel):
    model_config = {"frozen": True}

    valid: bool
    language: Language | None = None
    script: Script | None = None
    variant: SerbianVariant | None = None
    confidence: float = Field(ge=0, le=1)
    issues: tuple[str, ...] = ()

