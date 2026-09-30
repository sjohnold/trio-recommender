"""Queue, first-content, total timeout, and overload handling."""
import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from trio.inference.protocol import (
    ChunkKind,
    InferenceResult,
    ResultStatus,
    TokenChunk,
)
@dataclass(frozen=True, slots=True)
class TimeoutLimits:
    queue_seconds: float
    first_token_seconds: float
    total_seconds: float

    def __post_init__(self) -> None:
        if min(
            self.queue_seconds, self.first_token_seconds, self.total_seconds
        ) <= 0:
            raise ValueError("all timeout limits must be positive")
@dataclass(frozen=True, slots=True)
class ResilienceRequest:
    request_id: str
    start: Callable[[], Awaitable[AsyncIterator[TokenChunk]]]
async def _close(stream: AsyncIterator[TokenChunk]) -> None:
    closer = getattr(stream, "aclose", None)
    if closer is not None:
        await closer()
async def run_with_limits(
    request: ResilienceRequest, limits: TimeoutLimits
) -> InferenceResult:
    try:
        stream = await asyncio.wait_for(request.start(), limits.queue_seconds)
    except TimeoutError:
        return InferenceResult(
            request.request_id, ResultStatus.FAILED, "", error_code="queue_timeout"
        )
    iterator = aiter(stream)
    loop = asyncio.get_running_loop()
    started = loop.time()
    first_deadline = started + limits.first_token_seconds
    total_deadline = started + limits.total_seconds
    text = thinking = ""
    seen_content = False
    while True:
        now = loop.time()
        deadline = total_deadline
        reason = "total_timeout"
        if not seen_content and first_deadline < deadline:
            deadline, reason = first_deadline, "first_token_timeout"
        try:
            chunk = await asyncio.wait_for(anext(iterator), max(0, deadline - now))
        except TimeoutError:
            await _close(iterator)
            return InferenceResult(
                request.request_id, ResultStatus.FAILED, text, thinking, reason
            )
        except StopAsyncIteration:
            return InferenceResult(
                request.request_id, ResultStatus.FAILED, text, thinking,
                "incomplete_stream",
            )
        if chunk.kind is ChunkKind.CONTENT:
            text += chunk.text
            seen_content = True
        elif chunk.kind is ChunkKind.THINKING:
            thinking += chunk.text
        elif chunk.kind is ChunkKind.ERROR:
            code = chunk.error_code or "stream_error"
            if code == "http_error" and "503" in chunk.text:
                code = "ollama_overloaded"
            return InferenceResult(
                request.request_id, ResultStatus.FAILED, text, thinking, code
            )
        elif chunk.kind is ChunkKind.DONE:
            return InferenceResult(
                request.request_id, ResultStatus.COMPLETED, text, thinking
            )
