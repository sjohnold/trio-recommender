import sys
from dataclasses import fields
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trio.contracts import Role
from trio.orchestrator.context import ContextInput, PromptParts, build_context


def context() -> ContextInput:
    return ContextInput(
        Role.PRAGMATIST,
        ("Never invent facts.", "Never attack a person."),
        "Practical anchor.",
        ("Use one concrete next step.",),
        ("Example one.", "Example two."),
        '{"tension":"unknown"}',
        {
            Role.PRAGMATIST: ("pragmatist private memory",),
            Role.LOGICIAN: ("logician private memory",),
            Role.EMPATH: ("empath private memory",),
        },
        ("The user addressed this role.",),
        "Current user event.",
        128,
    )


def test_context_contains_all_sections_and_role_scoped_memory() -> None:
    parts = build_context(context(), 4096)
    kinds = {part.kind for part in parts.parts}
    assert kinds == {
        "unconditional", "role_anchor", "rules", "examples", "state",
        "role_memory", "addressed_turns", "event",
    }
    text = "\n".join(part.text for part in parts.parts)
    assert "pragmatist private memory" in text
    assert "logician private memory" not in text
    assert parts.used_tokens + parts.reserve_output <= 4096


def test_priority_trimming_preserves_safety_anchor_and_event() -> None:
    value = context()
    mandatory_budget = sum(
        len(text.encode()) + 4
        for text in (*value.unconditional, value.role_anchor, value.event)
    )
    parts = build_context(value, mandatory_budget + value.reserve_output)
    assert [part.kind for part in parts.parts] == [
        "unconditional", "unconditional", "role_anchor", "event",
    ]
    assert parts.dropped
    assert parts.used_tokens + parts.reserve_output <= (
        mandatory_budget + value.reserve_output
    )


def test_no_full_transcript_input_and_reserve_is_required() -> None:
    assert "transcript" not in {field.name for field in fields(ContextInput)}
    with pytest.raises(ValueError, match="output reserve"):
        build_context(context(), 100)
