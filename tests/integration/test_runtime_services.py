import json
from pathlib import Path

import httpx

from trio.api.services import RuntimeServices
from trio.inference.protocol import ChunkKind, TokenChunk
from trio.settings import Settings
from trio.state.client import RawStateResult
from trio.storage.database import Database


class Backend:
    def __init__(self):
        self.requests = []
        self.failed_empath_once = False

    async def stream(self, request):
        self.requests.append(request)
        prompt = request.messages[0].content
        if "You play Мира" in prompt and not self.failed_empath_once:
            self.failed_empath_once = True
            yield TokenChunk(
                request.request_id, ChunkKind.ERROR, "context overload",
                "context_overload",
            )
            return
        # Keep the mock above the runtime's minimum accepted response length.
        yield TokenChunk(request.request_id, ChunkKind.CONTENT, "local model reply")
        yield TokenChunk(request.request_id, ChunkKind.DONE, "{}")


async def state_infer(prompt, model, timeout):
    assert model == "state:latest"
    return RawStateResult(json.dumps({
        "tension": "unknown",
        "trend": "unknown",
        "relations": [],
        "topic_shift": {"detected": "unknown", "confidence": 0},
        "user_signal": {
            "valence": "unknown", "arousal": "unknown",
            "stance": "unknown", "confidence": 0,
        },
        "suggested_next": "unknown",
    }), (), 1)


def snapshot():
    preset = json.loads(
        (Path(__file__).parents[2] / "data/presets/default-trio.json").read_text()
    )
    return {
        "mode": "B",
        "actor_models": ["actor:latest"],
        "state_model": "state:latest",
        "model_digests": {
            "actor:latest": "sha256:actor",
            "state:latest": "sha256:state",
        },
        "profile": "Base",
        "language_lock": {
            "language": "en", "script": "Latn", "variant": None,
        },
        "ablations": {"stage1": True, "stage2": True, "stage3": True},
        "personas": preset["personas"],
    }


async def test_local_vertical_models_session_stream_and_metrics(tmp_path):
    def tags(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [
            {
                "name": "actor:latest", "digest": "sha256:actor",
                "size": 3 * 1024**3, "details": {"family": "actor"},
            },
            {
                "name": "state:latest", "digest": "sha256:state",
                "size": 512 * 1024**2, "details": {"family": "state"},
            },
        ]})

    services = RuntimeServices(
        Settings(database_path=tmp_path / "trio.db"), state_infer=state_infer
    )
    async with Database.open(tmp_path / "trio.db") as database:
        await services.start(database)
        await services._client.aclose()
        services._client = httpx.AsyncClient(
            transport=httpx.MockTransport(tags), trust_env=False
        )
        backend = Backend()
        services._backend = backend
        try:
            assert len(await services.models()) == 2
            saved = await services.save_preset({
                "id": "research-trio",
                "preset": {
                    "version": "1.0.0",
                    "personas": snapshot()["personas"],
                },
            })
            assert saved["revision"] == 1
            saved_again = await services.save_preset({
                "id": "research-trio",
                "preset": {
                    "version": "1.0.0",
                    "personas": snapshot()["personas"],
                },
            })
            assert saved_again["revision"] == 2
            listed = await services.list_presets()
            assert [item["id"] for item in listed] == [
                "default-trio", "research-trio",
            ]
            assert listed[1]["revision"] == 2
            assert (await services.admission(snapshot()))["admitted"]
            await services.admit(snapshot())
            session_id = await services.sessions.create_session(snapshot())
            events = [
                event async for event in services.stream(session_id, "Hello")
            ]
            chunks = [event for event in events if event["kind"] == "chunk"]
            completed = [
                event for event in events
                if event["kind"] == "utterance"
                and event["payload"].get("state") == "COMPLETED"
            ]
            assert len(completed) == 3
            assert {event["payload"]["role"] for event in chunks} == {
                "pragmatist", "logician", "empath",
            }
            assert sum(
                event["payload"]["text"] == "local model reply" for event in chunks
            ) == 3
            assert backend.failed_empath_once
            assert len(backend.requests) == 4
            empath_prompt = next(
                request.messages[0].content for request in backend.requests
                if "You play Мира" in request.messages[0].content
            )
            assert "speak gently" in empath_prompt
            assert "grew up in Novi Sad" in empath_prompt
            empath_request = next(
                request for request in backend.requests
                if "You play Мира" in request.messages[0].content
            )
            assert empath_request.messages[2].content.startswith("Мира.")
            metrics = await services.metrics(session_id)
            assert metrics["mode"] == "B"
            assert metrics["ttft"]["p50"] is not None
            assert metrics["full"]["p95"] is not None
            assert metrics["stateFallbackRate"] == 0
        finally:
            await services.stop()
