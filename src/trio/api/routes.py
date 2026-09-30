"""Same-origin local REST and WebSocket routes."""
import asyncio
import json
from contextlib import suppress

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

MAX_PAYLOAD = 16_384


def create_router(services) -> APIRouter:
    router = APIRouter()

    @router.get("/api/models")
    async def models():
        try:
            return await services.models()
        except ConnectionError as error:
            raise HTTPException(503, detail=str(error)) from error

    @router.get("/api/presets")
    async def presets():
        return await services.list_presets()

    @router.post("/api/presets")
    async def save_preset(body: dict):
        try:
            return await services.save_preset(body)
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error

    @router.post("/api/admission")
    async def admission(body: dict):
        try:
            return await services.admission(body)
        except ConnectionError as error:
            raise HTTPException(503, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error

    @router.post("/api/recommendations/voice-examples")
    async def recommend_voice_examples(body: dict):
        """Inspect ranked candidates and the diversified top-k selection."""
        try:
            return services.recommend_voice_examples(body)
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error

    @router.post("/api/sessions", status_code=201)
    async def create_session(body: dict):
        try:
            await services.admit(body)
            session_id = await services.sessions.create_session(body)
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error
        return {"session_id": session_id}
    @router.get("/api/sessions/{session_id}/metrics")
    async def metrics(session_id: str):
        if await services.sessions.get_session(session_id) is None:
            raise HTTPException(404, detail="session_not_found")
        return await services.metrics(session_id)

    @router.websocket("/ws/sessions/{session_id}")
    async def session_socket(socket: WebSocket, session_id: str):
        origin, host = socket.headers.get("origin"), socket.headers.get("host")
        if origin and origin not in {f"http://{host}", f"https://{host}"}:
            await socket.close(1008, "same_origin_required")
            return
        if await services.sessions.get_session(session_id) is None:
            await socket.close(4404, "session_not_found")
            return
        await socket.accept()
        sequence, stream_task = 0, None
        partial = {"text": "", "utterance_id": None, "role": None}
        send_lock = asyncio.Lock()

        async def send(kind: str, payload: dict):
            nonlocal sequence
            async with send_lock:
                sequence += 1
                envelope = {"kind": kind, "payload": payload, "sequence": sequence}
                encoded = json.dumps(envelope, ensure_ascii=False)
                if len(encoded.encode("utf-8")) > MAX_PAYLOAD:
                    await socket.close(1009, "outbound_payload_too_large")
                    raise WebSocketDisconnect()
                await socket.send_json(envelope)

        async def stream(text: str, target: str | None):
            try:
                async for event in services.stream(session_id, text, target):
                    payload = event.get("payload", {})
                    if event.get("kind") == "utterance" and payload.get("state") == "PLANNED":
                        partial.update({
                            "text": "",
                            "utterance_id": payload.get("utterance_id"),
                            "role": payload.get("role"),
                        })
                    elif event.get("kind") == "chunk":
                        partial["text"] += str(payload.get("text", ""))
                    await send(event["kind"], payload)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                await send("error", {"message": str(error)})

        async def interrupt() -> None:
            nonlocal stream_task
            if stream_task is None or stream_task.done():
                return
            await services.cancel(session_id)
            stream_task.cancel()
            with suppress(asyncio.CancelledError):
                await stream_task
            await services.persist_partial(session_id, dict(partial))
            if partial["utterance_id"]:
                await send("utterance", {
                    "utterance_id": partial["utterance_id"],
                    "role": partial["role"],
                    "state": "INTERRUPTED",
                    "reason": "user_interrupt",
                })
            await send("state", {"phase": "round_completed"})
            partial.update({"text": "", "utterance_id": None, "role": None})
            stream_task = None

        try:
            while True:
                raw = await socket.receive_text()
                if len(raw.encode("utf-8")) > MAX_PAYLOAD:
                    await socket.close(1009, "payload_too_large")
                    return
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    await socket.close(1003, "invalid_json")
                    return
                action = message.get("action") or message.get("kind")
                if action in {"message", "user"}:
                    payload = message.get("payload", {})
                    text = payload.get("text") if isinstance(payload, dict) else None
                    if not isinstance(text, str) or not text.strip():
                        await send("error", {"message": "message text is required"})
                        continue
                    if stream_task and not stream_task.done():
                        await interrupt()
                    target = payload.get("target")
                    stream_task = asyncio.create_task(stream(text, target))
                elif action == "cancel":
                    await interrupt()
                elif action == "persona_update":
                    try:
                        result = await services.update_live_stats(session_id, message)
                        await send("state", {"phase": "persona_updated", **result})
                    except ValueError as error:
                        await send("error", {"message": str(error)})
                else:
                    await send("error", {"message": "unsupported_action"})
        except WebSocketDisconnect:
            if stream_task and not stream_task.done():
                stream_task.cancel()
                with suppress(asyncio.CancelledError):
                    await stream_task

    return router
