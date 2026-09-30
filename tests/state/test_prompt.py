import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trio.state.prompt import (
    MAX_OUTPUT_TOKENS,
    MAX_PROMPT_CHARS,
    build_state_prompt,
)


@pytest.mark.parametrize("language", ["ru", "en", "sr"])
def test_prompt_is_localized_bounded_and_contains_schema(language: str) -> None:
    prompt = build_state_prompt(
        [{"speaker": "user", "text": "I disagree"}, {"speaker": "logician", "text": "Why?"}],
        {"tension": "unknown"},
        language,
    )
    assert '"tension"' in prompt.user
    assert '"user_signal"' in prompt.user
    assert "unknown" in prompt.user
    assert len(prompt.user) <= MAX_PROMPT_CHARS
    assert prompt.max_output_tokens == MAX_OUTPUT_TOKENS
    assert prompt.schema["additionalProperties"] is False


def test_prompt_uses_only_recent_bounded_observations() -> None:
    events = [{"index": index, "text": "x" * 2_000} for index in range(20)]
    prompt = build_state_prompt(events, {"raw": "y" * 4_000}, "en")
    assert '"truncated": true' in prompt.user
    assert '"index":0' not in prompt.user
    assert len(prompt.user) <= MAX_PROMPT_CHARS


def test_prompt_forbids_inference_and_rejects_unknown_locale() -> None:
    prompt = build_state_prompt([], None, "en")
    assert "Do not diagnose or infer hidden intentions" in prompt.user
    with pytest.raises(ValueError, match="unsupported prompt language"):
        build_state_prompt([], None, "de")
