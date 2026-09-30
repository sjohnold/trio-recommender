import asyncio
import json
import sys
from pathlib import Path
from starlette.websockets import WebSocketDisconnect
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.api.routes import create_router
class Sessions:
    def __init__(self, owner):
        self.owner, self.data = owner, {}
    async def create_session(self, snapshot):
        self.owner.calls.append("create")
        self.data["s1"] = snapshot
        return "s1"
    async def get_session(self, session_id): return self.data.get(session_id)
class Services:
    def __init__(self):
        self.calls, self.partial, self.sessions = [], None, Sessions(self)
    async def admit(self, snapshot): self.calls.append("admit")
    async def list_presets(self): return [{"id": "p"}]
    async def save_preset(self, body): return {"version": 1}
    async def metrics(self, session_id): return {"session_id": session_id}
    async def stream(self, session_id, text, target=None):
        assert text == "hello" and target is None
        yield {"kind": "utterance", "payload": {
            "utterance_id": "u1", "role": "empath", "state": "PLANNED",
        }}
        yield {"kind": "chunk", "payload": {
            "utterance_id": "u1", "role": "empath", "text": "partial",
        }}
        await asyncio.sleep(1)
    async def cancel(self, session_id): self.calls.append("cancel")
    async def persist_partial(self, session_id, partial): self.partial = partial
class Socket:
    def __init__(self, origin="http://testserver"):
        self.headers = {"origin": origin, "host": "testserver"}
        self.sent, self.closed, self.receives = [], None, 0
    async def accept(self): pass
    async def close(self, code, reason): self.closed = (code, reason)
    async def send_json(self, payload): self.sent.append(payload)
    async def receive_text(self):
        self.receives += 1
        if self.receives == 1:
            return json.dumps({"kind": "user", "payload": {"text": "hello"}})
        if self.receives == 2:
            await asyncio.sleep(.01)
            return json.dumps({"kind": "cancel"})
        raise WebSocketDisconnect()
def endpoint(router, path, method=None):
    return next(route.endpoint for route in router.routes if route.path == path
                and (method is None or method in route.methods))
def test_rest_admits_before_session_and_exposes_presets_metrics():
    async def check():
        services = Services(); router = create_router(services)
        assert await endpoint(router, "/api/presets", "GET")() == [{"id": "p"}]
        assert await endpoint(router, "/api/presets", "POST")({}) == {"version": 1}
        result = await endpoint(router, "/api/sessions", "POST")({})
        assert result == {"session_id": "s1"} and services.calls == ["admit", "create"]
        assert await endpoint(router, "/api/sessions/{session_id}/metrics", "GET")("s1") == {"session_id": "s1"}
    asyncio.run(check())
def test_ws_stream_cancel_partial_sequence_and_same_origin():
    async def check():
        services = Services()
        router, socket = create_router(services), Socket()
        await services.sessions.create_session({})
        ws = endpoint(router, "/ws/sessions/{session_id}")
        await ws(socket, "s1")
        assert [(item["sequence"], item.get("kind")) for item in socket.sent] == [
            (1, "utterance"), (2, "chunk"), (3, "utterance"), (4, "state")]
        assert socket.sent[-2]["payload"]["state"] == "INTERRUPTED"
        assert socket.sent[-1]["payload"]["phase"] == "round_completed"
        assert services.partial == {
            "text": "partial", "utterance_id": "u1", "role": "empath",
        }
        assert services.calls[-1] == "cancel"
        bad = Socket("http://evil")
        await ws(bad, "s1")
        assert bad.closed == (1008, "same_origin_required")
    asyncio.run(check())
