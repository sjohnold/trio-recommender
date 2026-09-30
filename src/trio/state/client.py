"""Structured, loopback-only State Model client."""
import json
from dataclasses import dataclass
from typing import Any

import httpx

from trio.settings import Settings
from trio.state.prompt import StatePrompt
_DURATION_KEYS = {
    "total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
}


class StateInferenceError(RuntimeError):
    def __init__(self, message: str, raw_json: str = "", durations=()) -> None:
        super().__init__(message)
        self.raw_json = raw_json
        self.durations = tuple(durations)


@dataclass(frozen=True, slots=True)
class RawStateResult:
    raw_json: str
    durations: tuple[dict[str, int | float], ...]
    attempts: int


async def _post(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        value = response.json()
    if not isinstance(value, dict):
        raise StateInferenceError("Ollama response must be a JSON object")
    return value


def _payload(prompt: StatePrompt, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": prompt.user},
        ],
        "format": prompt.schema,
        "stream": False,
        "think": False,
        "keep_alive": -1,
        "options": {
            "num_predict": prompt.max_output_tokens,
            "temperature": 0,
            "seed": 0,
        },
    }


async def infer_state(
    prompt: StatePrompt, model: str, timeout: float
) -> RawStateResult:
    if not model.strip():
        raise ValueError("model must not be empty")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    url = f"{Settings.load().ollama_url}/api/chat"
    payload = _payload(prompt, model)
    durations: list[dict[str, int | float]] = []
    raw = ""
    for attempt in (1, 2):
        try:
            response = await _post(url, payload, timeout)
            raw = response["message"]["content"]
            if not isinstance(raw, str) or not isinstance(json.loads(raw), dict):
                raise ValueError("model content must be a JSON object")
            durations.append({
                key: response[key] for key in _DURATION_KEYS if key in response
            })
            return RawStateResult(raw, tuple(durations), attempt)
        except (KeyError, TypeError, json.JSONDecodeError, ValueError) as error:
            durations.append({
                key: response[key] for key in _DURATION_KEYS
                if "response" in locals() and key in response
            })
            if attempt == 2:
                raise StateInferenceError(
                    f"invalid state JSON after repair: {error}", raw, durations
                ) from error
            payload["messages"].extend([
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "Repair the response. Return exactly one JSON object matching "
                    "the supplied schema; use unknown when evidence is ambiguous."
                )},
            ])
    raise AssertionError("unreachable")
