import asyncio
import sys
from pathlib import Path
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trio.inference.cancellation import CancellationRegistry, InterruptReason
from trio.inference.protocol import ChunkKind, TokenChunk
async def source(request_id, first, release, closed):
    try:
        yield TokenChunk(request_id, ChunkKind.CONTENT, first)
        await release.wait()
        yield TokenChunk(request_id, ChunkKind.CONTENT, "done")
        yield TokenChunk(request_id, ChunkKind.DONE)
    finally:
        closed.set()
def test_cancel_is_per_request_preserves_partial_and_closes_stream() -> None:
    async def run():
        registry = CancellationRegistry()
        release_one, release_two = asyncio.Event(), asyncio.Event()
        closed_one, closed_two = asyncio.Event(), asyncio.Event()
        seen_one, seen_two = [], []
        async def consume(target, seen):
            async for chunk in target:
                seen.append(chunk.text)
        one = registry.stream("one", source("one", "A", release_one, closed_one))
        two = registry.stream("two", source("two", "B", release_two, closed_two))
        task_one = asyncio.create_task(consume(one, seen_one))
        task_two = asyncio.create_task(consume(two, seen_two))
        await asyncio.sleep(0)
        assert registry.cancel("one", InterruptReason.ORCHESTRATOR)
        await task_one
        assert await asyncio.wait_for(closed_one.wait(), 1)
        assert not task_two.done()
        release_two.set()
        await task_two
        return registry, seen_one, seen_two, closed_two
    registry, seen_one, seen_two, closed_two = asyncio.run(run())
    result = registry.result("one")
    assert result is not None
    assert result.text == "A" and result.reason == "orchestrator_interrupt"
    assert seen_one == ["A"] and seen_two == ["B", "done", ""]
    assert closed_two.is_set()
def test_unknown_or_repeated_cancel_returns_false() -> None:
    async def run():
        registry = CancellationRegistry()
        release, closed = asyncio.Event(), asyncio.Event()
        task = asyncio.create_task(_drain(
            registry.stream("one", source("one", "A", release, closed))
        ))
        await asyncio.sleep(0)
        assert registry.cancel("missing") is False
        assert registry.cancel("one") is True
        assert registry.cancel("one") is False
        await task
        return registry.result("one")
    assert asyncio.run(run()).reason == "user_interrupt"
async def _drain(stream):
    async for _ in stream:
        pass
