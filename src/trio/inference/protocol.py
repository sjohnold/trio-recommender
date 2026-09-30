"""Backend-neutral inference contracts."""
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from trio.persona.generation import InferenceOptions
class ChunkKind(StrEnum):
    CONTENT = "content"
    THINKING = "thinking"
    DONE = "done"
    ERROR = "error"
class ResultStatus(StrEnum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
class CancelOutcome(StrEnum):
    REQUESTED = "requested"
    NOT_FOUND = "not_found"
    ALREADY_DONE = "already_done"
@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"} or not self.content:
            raise ValueError("message requires a supported role and non-empty content")
@dataclass(frozen=True, slots=True)
class InferenceRequest:
    request_id: str
    model: str
    messages: tuple[ChatMessage, ...]
    options: InferenceOptions

    def __post_init__(self) -> None:
        if not self.request_id or not self.model or not self.messages:
            raise ValueError("request_id, model, and messages are required")
@dataclass(frozen=True, slots=True)
class TokenChunk:
    request_id: str
    kind: ChunkKind
    text: str = ""
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id is required")
        if self.kind in {ChunkKind.CONTENT, ChunkKind.THINKING} and not self.text:
            raise ValueError("text chunks must not be empty")
        if self.kind is ChunkKind.ERROR and not self.error_code:
            raise ValueError("error chunks require error_code")
        if self.kind is not ChunkKind.ERROR and self.error_code is not None:
            raise ValueError("only error chunks may carry error_code")
@dataclass(frozen=True, slots=True)
class InferenceResult:
    request_id: str
    status: ResultStatus
    text: str
    thinking: str = ""
    error_code: str | None = None
@dataclass(frozen=True, slots=True)
class LoadedModel:
    name: str
    digest: str
    family: str
    resident_bytes: int
class InferenceBackend(Protocol):
    def stream(self, request: InferenceRequest) -> AsyncIterator[TokenChunk]:
        ...
    async def cancel(self, request_id: str) -> CancelOutcome:
        ...
    async def loaded_models(self) -> tuple[LoadedModel, ...]:
        ...
