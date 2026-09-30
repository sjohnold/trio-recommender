"""Async streaming adapter for Ollama's loopback NDJSON chat API."""
import json
from dataclasses import asdict
import httpx
from trio.inference.protocol import ChunkKind, InferenceRequest, TokenChunk
from trio.settings import Settings
_STATS = {
    "total_duration", "load_duration", "prompt_eval_count",
    "prompt_eval_duration", "eval_count", "eval_duration",
}
class OllamaBackend:
    def __init__(
        self, settings: Settings | None = None, client: httpx.AsyncClient | None = None
    ) -> None:
        self.settings = settings or Settings.load()
        self.client = client

    async def stream(self, request: InferenceRequest):
        options = asdict(request.options)
        system = request.messages[0].content if request.messages else ""
        if (
            "ИМПРОВИЗАЦИОННАЯ СЦЕНА" in system
            or "IMPROVISED SCENE" in system
        ):
            options["stop"] = [
                "Я — программа", "Я – программа", "Я программа", "Я создан",
                "Я создана", "Моя задача", "моя задача", "Я — система",
                "Я – система", "Я система", "Я — ИИ", "Я – ИИ",
                "I am a program", "I'm a program", "I am an AI", "I'm an AI",
                "As an AI", "My task", "my task",
                "Vector (pragmatist):", "Axiom (logician):",
                "Resonance (empath):",
                "Вера (pragmatist):", "Алексей (logician):",
                "Мира (empath):",
            ]
        payload = {
            "model": request.model,
            "messages": [asdict(message) for message in request.messages],
            "options": options,
            "stream": True,
            "think": False,
            "keep_alive": -1,
        }
        client = self.client or httpx.AsyncClient()
        owned = self.client is None
        try:
            async with client.stream(
                "POST", f"{self.settings.ollama_url}/api/chat", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        if not isinstance(chunk, dict):
                            raise ValueError("chunk is not an object")
                        if "error" in chunk:
                            yield TokenChunk(
                                request.request_id, ChunkKind.ERROR,
                                str(chunk["error"]), "ollama_error",
                            )
                            return
                        message = chunk.get("message", {})
                        if not isinstance(message, dict):
                            raise ValueError("message is not an object")
                        thinking = message.get("thinking", "")
                        content = message.get("content", "")
                        if not isinstance(thinking, str) or not isinstance(content, str):
                            raise ValueError("token fields are not strings")
                        if thinking:
                            yield TokenChunk(
                                request.request_id, ChunkKind.THINKING, thinking
                            )
                        if content:
                            yield TokenChunk(
                                request.request_id, ChunkKind.CONTENT, content
                            )
                        if chunk.get("done") is True:
                            stats = {
                                key: chunk[key] for key in _STATS if key in chunk
                            }
                            yield TokenChunk(
                                request.request_id, ChunkKind.DONE,
                                json.dumps(stats, sort_keys=True),
                            )
                            return
                    except (json.JSONDecodeError, TypeError, ValueError):
                        yield TokenChunk(
                            request.request_id, ChunkKind.ERROR, line,
                            "invalid_ndjson_chunk",
                        )
                        return
                yield TokenChunk(
                    request.request_id, ChunkKind.ERROR, "",
                    "incomplete_stream",
                )
        except httpx.HTTPError as error:
            yield TokenChunk(
                request.request_id, ChunkKind.ERROR, str(error), "http_error"
            )
        finally:
            if owned:
                await client.aclose()
