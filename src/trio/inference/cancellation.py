"""Per-request cancellation for streaming inference."""
import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from trio.inference.protocol import ChunkKind, TokenChunk
class InterruptReason(StrEnum):
    USER = "user_interrupt"
    ORCHESTRATOR = "orchestrator_interrupt"
@dataclass(frozen=True, slots=True)
class CancellationResult:
    request_id: str
    text: str
    reason: InterruptReason
@dataclass(slots=True)
class _Scope:
    request_id: str
    source: AsyncIterator[TokenChunk]
    task: asyncio.Task | None = None
    reason: InterruptReason | None = None
    text: str = ""
class CancellationRegistry:
    def __init__(self) -> None:
        self._active: dict[str, _Scope] = {}
        self._results: dict[str, CancellationResult] = {}

    def stream(
        self, request_id: str, source: AsyncIterator[TokenChunk]
    ) -> AsyncIterator[TokenChunk]:
        if not request_id or request_id in self._active:
            raise ValueError("request_id must be non-empty and unique")
        scope = _Scope(request_id, source)
        self._active[request_id] = scope
        return self._consume(scope)

    async def _consume(self, scope: _Scope):
        scope.task = asyncio.current_task()
        try:
            async for chunk in scope.source:
                if chunk.kind is ChunkKind.CONTENT:
                    scope.text += chunk.text
                yield chunk
        except asyncio.CancelledError:
            if scope.reason is None:
                raise
        finally:
            self._active.pop(scope.request_id, None)
            if scope.reason is not None:
                self._results[scope.request_id] = CancellationResult(
                    scope.request_id, scope.text, scope.reason
                )

    def cancel(
        self,
        request_id: str,
        reason: InterruptReason = InterruptReason.USER,
    ) -> bool:
        scope = self._active.get(request_id)
        if scope is None or scope.reason is not None:
            return False
        scope.reason = reason
        if scope.task is not None:
            scope.task.cancel()
        return True

    def result(self, request_id: str) -> CancellationResult | None:
        return self._results.get(request_id)
