"""Monotonic latency measurement for inference streams."""
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from time import monotonic
from trio.inference.protocol import ChunkKind, TokenChunk
@dataclass(frozen=True, slots=True)
class LatencySample:
    ttft_ms: float | None
    total_ms: float
    load_ms: float | None
    eval_ms: float | None
class TimedStream:
    def __init__(
        self,
        source: AsyncIterator[TokenChunk],
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.source = source
        self.clock = clock
        self.queued_at = clock()
        self.started_at: float | None = None
        self.first_content_at: float | None = None
        self.done_at: float | None = None
        self.load_ms: float | None = None
        self.eval_ms: float | None = None

    async def __aiter__(self):
        if self.started_at is not None:
            raise RuntimeError("timed stream may only be consumed once")
        self.started_at = self.clock()
        try:
            async for chunk in self.source:
                if (
                    chunk.kind is ChunkKind.CONTENT
                    and self.first_content_at is None
                ):
                    self.first_content_at = self.clock()
                if chunk.kind is ChunkKind.DONE:
                    self._read_stats(chunk.text)
                if chunk.kind in {ChunkKind.DONE, ChunkKind.ERROR}:
                    self.done_at = self.clock()
                yield chunk
                if self.done_at is not None:
                    return
        finally:
            if self.done_at is None:
                self.done_at = self.clock()

    def _read_stats(self, text: str) -> None:
        try:
            stats = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return
        if isinstance(stats, dict):
            if isinstance(stats.get("load_duration"), (int, float)):
                self.load_ms = stats["load_duration"] / 1_000_000
            if isinstance(stats.get("eval_duration"), (int, float)):
                self.eval_ms = stats["eval_duration"] / 1_000_000

    @property
    def sample(self) -> LatencySample:
        if self.done_at is None:
            raise RuntimeError("latency sample is not complete")
        first = self.first_content_at
        return LatencySample(
            None if first is None else (first - self.queued_at) * 1000,
            (self.done_at - self.queued_at) * 1000,
            self.load_ms,
            self.eval_ms,
        )
