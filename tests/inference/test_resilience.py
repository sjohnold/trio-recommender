import asyncio
import sys
from pathlib import Path
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trio.inference.protocol import ChunkKind, ResultStatus, TokenChunk
from trio.inference.resilience import (
    ResilienceRequest,
    TimeoutLimits,
    run_with_limits,
)
def run(factory, limits=(0.02, 0.02, 0.03)):
    request = ResilienceRequest("r", factory)
    return asyncio.run(run_with_limits(request, TimeoutLimits(*limits)))


async def delayed_start():
    await asyncio.sleep(0.02)
    return tokens()


async def tokens(*items):
    for item in items:
        if isinstance(item, float):
            await asyncio.sleep(item)
        else:
            yield item


def test_queue_and_first_token_timeouts_are_distinct() -> None:
    queued = run(delayed_start, (0.001, 1, 1))
    async def first_token():
        return tokens(TokenChunk("r", ChunkKind.THINKING, "h"), 0.02)
    first = run(first_token, (1, 0.001, 1))
    assert queued.error_code == "queue_timeout"
    assert first.error_code == "first_token_timeout"
    assert queued.status is first.status is ResultStatus.FAILED


def test_total_timeout_preserves_partial_text() -> None:
    async def start():
        return tokens(TokenChunk("r", ChunkKind.CONTENT, "partial"), 0.02)
    result = run(start, (1, 1, 0.001))
    assert result.error_code == "total_timeout"
    assert result.text == "partial"


def test_ollama_503_is_visible_and_session_can_continue() -> None:
    async def overloaded():
        return tokens(TokenChunk(
            "r", ChunkKind.ERROR, "503 Service Unavailable", "http_error"
        ))
    failed = run(overloaded)
    assert failed.error_code == "ollama_overloaded"
    async def healthy():
        return tokens(
            TokenChunk("r", ChunkKind.CONTENT, "ok"),
            TokenChunk("r", ChunkKind.DONE),
        )
    recovered = run(healthy)
    assert recovered.status is ResultStatus.COMPLETED
    assert recovered.text == "ok"
