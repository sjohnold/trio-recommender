import asyncio
import sys
from pathlib import Path
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trio.inference.protocol import ChunkKind, TokenChunk
from trio.inference.timing import TimedStream
class Clock:
    def __init__(self):
        self.value = -1
    def __call__(self):
        self.value += 1
        return self.value
async def chunks(*values):
    for value in values:
        yield value
def consume(timed):
    async def run():
        return [chunk async for chunk in timed]
    return asyncio.run(run())
def test_thinking_does_not_count_as_first_content() -> None:
    timed = TimedStream(chunks(
        TokenChunk("r", ChunkKind.THINKING, "hmm"),
        TokenChunk("r", ChunkKind.CONTENT, "answer"),
        TokenChunk(
            "r", ChunkKind.DONE,
            '{"load_duration":2000000,"eval_duration":5000000}',
        ),
    ), Clock())
    consume(timed)
    assert timed.sample.ttft_ms == 2000
    assert timed.sample.total_ms == 3000
    assert timed.sample.load_ms == 2 and timed.sample.eval_ms == 5
def test_zero_answer_has_no_ttft_but_has_total() -> None:
    timed = TimedStream(chunks(TokenChunk("r", ChunkKind.DONE, "{}")), Clock())
    consume(timed)
    assert timed.sample.ttft_ms is None
    assert timed.sample.total_ms == 2000
def test_error_has_meaningful_terminal_metrics() -> None:
    timed = TimedStream(
        chunks(TokenChunk("r", ChunkKind.ERROR, "", "http_error")), Clock()
    )
    consume(timed)
    assert timed.sample.ttft_ms is None
    assert timed.sample.total_ms == 2000
