import asyncio
import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trio.state import client
from trio.state.prompt import build_state_prompt

PROMPT = build_state_prompt([], None, "en")


def test_structured_request_and_raw_durations_are_preserved(monkeypatch) -> None:
    calls = []
    async def fake_post(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {"message": {"content": json.dumps({"tension": "unknown"})},
                "total_duration": 12, "eval_duration": 4}
    monkeypatch.setattr(client, "_post", fake_post)
    result = asyncio.run(client.infer_state(PROMPT, "state-model", 3.0))
    assert result.raw_json == '{"tension": "unknown"}'
    assert result.durations == ({"total_duration": 12, "eval_duration": 4},)
    assert result.attempts == 1
    url, payload, timeout = calls[0]
    assert url == "http://127.0.0.1:11434/api/chat" and timeout == 3.0
    assert payload["format"] == PROMPT.schema
    assert payload["stream"] is payload["think"] is False
    assert payload["keep_alive"] == -1
    assert payload["options"]["temperature"] == 0
    assert payload["options"]["seed"] == 0


def test_repairs_once_and_never_retries_twice(monkeypatch) -> None:
    replies = iter([
        {"message": {"content": "broken"}, "total_duration": 2},
        {"message": {"content": "{}"}, "total_duration": 3},
    ])
    calls = []
    async def fake_post(url, payload, timeout):
        calls.append(payload["messages"].copy())
        return next(replies)
    monkeypatch.setattr(client, "_post", fake_post)
    result = asyncio.run(client.infer_state(PROMPT, "state-model", 1))
    assert result.attempts == 2 and len(calls) == 2
    assert result.durations == ({"total_duration": 2}, {"total_duration": 3})
    assert "Repair the response" in calls[1][-1]["content"]


def test_second_invalid_response_is_typed_error(monkeypatch) -> None:
    calls = 0
    async def fake_post(url, payload, timeout):
        nonlocal calls
        calls += 1
        return {"message": {"content": "not-json"}}
    monkeypatch.setattr(client, "_post", fake_post)
    with pytest.raises(client.StateInferenceError, match="after repair"):
        asyncio.run(client.infer_state(PROMPT, "state-model", 1))
    assert calls == 2
