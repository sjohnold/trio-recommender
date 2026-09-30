"""Dependency-free domain identifiers shared by Trio modules."""

from enum import StrEnum
from typing import NewType


class Mode(StrEnum):
    A = "A"
    B = "B"


class Language(StrEnum):
    RU = "ru"
    EN = "en"
    SR = "sr"


class Role(StrEnum):
    PRAGMATIST = "pragmatist"
    LOGICIAN = "logician"
    EMPATH = "empath"


SessionId = NewType("SessionId", str)
PersonaId = NewType("PersonaId", str)
EventId = NewType("EventId", str)
UtteranceId = NewType("UtteranceId", str)
