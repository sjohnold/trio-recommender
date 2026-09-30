"""One-turn smoke test against a running local Trio backend and Ollama."""

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).parents[1]
HTTP = os.environ.get("TRIO_SMOKE_HTTP", "http://127.0.0.1:8000").rstrip("/")
WS = HTTP.replace("http://", "ws://", 1).replace("https://", "wss://", 1)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("A", "B"), default="A",
        help="A uses three actor model families; B uses one actor model.",
    )
    parser.add_argument(
        "--language", choices=("ru", "en"), default="en",
    )
    parser.add_argument(
        "--prompt",
        default="In one short sentence, say that the local Trio runtime works.",
    )
    return parser.parse_args()


def mode_a_actors(models: list[dict], state_name: str) -> list[dict]:
    actors: list[dict] = []
    for model in sorted(models, key=lambda item: item["size"]):
        if (
            model["name"] != state_name
            and all(actor["family"] != model["family"] for actor in actors)
        ):
            actors.append(model)
        if len(actors) == 3:
            return actors
    raise RuntimeError("Mode A requires three installed actor model families")


async def main(mode: str, language: str, prompt: str) -> None:
    preset = json.loads(
        (ROOT / "data/presets/default-trio.json").read_text(encoding="utf-8")
    )
    async with httpx.AsyncClient(base_url=HTTP, timeout=180) as client:
        models = (await client.get("/api/models")).raise_for_status().json()
        ordered = sorted(models, key=lambda model: model["size"])
        if len(ordered) < 2:
            raise RuntimeError("at least one actor and one separate State Model are required")
        state = ordered[0]
        actors = (
            mode_a_actors(models, state["name"])
            if mode == "A"
            else [next(model for model in ordered if model["name"] != state["name"])]
        )
        snapshot = {
            "mode": mode,
            "actor_models": [actor["name"] for actor in actors],
            "state_model": state["name"],
            "model_digests": {
                **{actor["name"]: actor["digest"] for actor in actors},
                state["name"]: state["digest"],
            },
            "profile": "Base",
            "language_lock": {
                "language": language,
                "script": "Cyrl" if language == "ru" else "Latn",
                "variant": None,
            },
            "ablations": {"stage1": True, "stage2": True, "stage3": True},
            "seed": 0,
            "personas": preset["personas"],
        }
        admission = (
            await client.post("/api/admission", json=snapshot)
        ).raise_for_status().json()
        if not admission["admitted"]:
            raise RuntimeError(f"admission blocked: {admission['reason']}")
        session = (
            await client.post("/api/sessions", json=snapshot)
        ).raise_for_status().json()

    print(
        f"session={session['session_id']} mode={mode} "
        f"actors={','.join(actor['name'] for actor in actors)} "
        f"state={state['name']}"
    )
    async with websockets.connect(
        f"{WS}/ws/sessions/{session['session_id']}", origin=HTTP
    ) as socket:
        await socket.send(json.dumps({
            "kind": "user",
            "payload": {
                "text": prompt,
                **({"target": "pragmatist"} if mode == "B" else {}),
            },
        }))
        completed: set[str] = set()
        nonempty: set[str] = set()
        started: set[str] = set()
        while True:
            event = json.loads(await socket.recv())
            if event["kind"] == "chunk":
                chunk = event["payload"].get("text", "")
                role = event["payload"]["role"]
                if role not in started:
                    print(f"\n[{role}] ", end="", flush=True)
                    started.add(role)
                print(chunk, end="", flush=True)
                if chunk.strip():
                    nonempty.add(role)
            if (
                event["kind"] == "utterance"
                and event["payload"].get("state") == "COMPLETED"
            ):
                completed.add(event["payload"]["role"])
            if (
                event["kind"] == "utterance"
                and event["payload"].get("state") == "FAILED"
            ):
                raise RuntimeError(event["payload"].get("reason", "generation failed"))
            if (
                event["kind"] == "state"
                and event["payload"].get("phase") == "round_completed"
            ):
                expected = 3 if mode == "A" else 1
                if len(completed) != expected:
                    raise RuntimeError(
                        f"expected {expected} completed actors, got {len(completed)}"
                    )
                if len(nonempty) != expected:
                    missing = sorted(completed - nonempty)
                    raise RuntimeError(
                        "completed actors returned empty text: "
                        + ",".join(missing)
                    )
                async with httpx.AsyncClient(base_url=HTTP, timeout=10) as client:
                    metrics = (
                        await client.get(
                            f"/api/sessions/{session['session_id']}/metrics"
                        )
                    ).raise_for_status().json()
                if metrics["stateFallbackRate"] != 0:
                    raise RuntimeError(
                        f"State Model fallback rate is {metrics['stateFallbackRate']}"
                    )
                print(
                    f"\ncompleted={','.join(sorted(completed))} "
                    f"stateFallbackRate={metrics['stateFallbackRate']}\nsmoke=PASS"
                )
                return


if __name__ == "__main__":
    options = arguments()
    asyncio.run(main(options.mode, options.language, options.prompt))
