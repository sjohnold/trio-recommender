import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trio.inference.ollama import OllamaBackend
from trio.inference.protocol import ChatMessage, ChunkKind, InferenceRequest
from trio.persona.generation import InferenceOptions
from trio.settings import Settings
class Response:
    def __init__(self, lines):
        self.lines = lines
        self.pulled = 0
    def raise_for_status(self):
        pass
    async def aiter_lines(self):
        for line in self.lines:
            self.pulled += 1
            yield line
class Client:
    def __init__(self, lines):
        self.response = Response(lines)
        self.payload = None
    @asynccontextmanager
    async def stream(self, method, url, json):
        self.payload = json
        yield self.response
def request() -> InferenceRequest:
    return InferenceRequest(
        "r1", "local-model", (ChatMessage("user", "Hello"),),
        InferenceOptions(0.5, 0.1, 1.1, 64, 4096),
    )
def test_yields_before_reading_full_body_and_keeps_order() -> None:
    async def run():
        client = Client([
            json.dumps({"message": {"content": "A"}, "done": False}),
            json.dumps({"message": {"content": "B"}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True,
                        "eval_count": 2, "total_duration": 9}),
        ])
        stream = OllamaBackend(Settings(), client).stream(request())
        first = await anext(stream)
        assert client.response.pulled == 1
        rest = [chunk async for chunk in stream]
        return client, [first, *rest]
    client, chunks = asyncio.run(run())
    assert [chunk.kind for chunk in chunks] == [
        ChunkKind.CONTENT, ChunkKind.CONTENT, ChunkKind.DONE,
    ]
    assert [chunk.text for chunk in chunks[:2]] == ["A", "B"]
    assert json.loads(chunks[-1].text) == {"eval_count": 2, "total_duration": 9}
    assert client.payload["stream"] is True
    assert client.payload["think"] is False and client.payload["keep_alive"] == -1
def test_broken_chunk_becomes_typed_error() -> None:
    async def run():
        backend = OllamaBackend(Settings(), Client(["{broken"]))
        return [chunk async for chunk in backend.stream(request())]
    chunks = asyncio.run(run())
    assert len(chunks) == 1
    assert chunks[0].kind is ChunkKind.ERROR
    assert chunks[0].error_code == "invalid_ndjson_chunk"


def test_persona_scene_stops_generic_assistant_self_description() -> None:
    async def run():
        client = Client([
            json.dumps({"message": {"content": ""}, "done": True}),
        ])
        persona_request = InferenceRequest(
            "r2", "local-model",
            (
                ChatMessage(
                    "system", "ИМПРОВИЗАЦИОННАЯ СЦЕНА. Ты играешь Vector."
                ),
                ChatMessage("user", "Кто ты?"),
            ),
            InferenceOptions(0.5, 0.1, 1.1, 64, 4096),
        )
        _ = [
            chunk async for chunk in
            OllamaBackend(Settings(), client).stream(persona_request)
        ]
        return client.payload

    payload = asyncio.run(run())
    assert "Я — программа" in payload["options"]["stop"]
    assert "Vector (pragmatist):" in payload["options"]["stop"]
