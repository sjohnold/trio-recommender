"""Priority-trimmed, role-scoped prompt context."""

from dataclasses import dataclass
from typing import Mapping

from trio.contracts import Role

_ORDER = {
    "unconditional": 0, "role_anchor": 1, "rules": 2, "examples": 3,
    "state": 4, "role_memory": 5, "addressed_turns": 6, "event": 7,
}


@dataclass(frozen=True, slots=True)
class ContextInput:
    role: Role
    unconditional: tuple[str, ...]
    role_anchor: str
    rules: tuple[str, ...]
    examples: tuple[str, ...]
    state: str
    role_memories: Mapping[Role, tuple[str, ...]]
    addressed_turns: tuple[str, ...]
    event: str
    reserve_output: int


@dataclass(frozen=True, slots=True)
class PromptPart:
    kind: str
    text: str
    tokens: int


@dataclass(frozen=True, slots=True)
class PromptParts:
    parts: tuple[PromptPart, ...]
    used_tokens: int
    reserve_output: int
    dropped: tuple[str, ...]


def _tokens(text: str) -> int:
    return len(text.encode("utf-8")) + 4


def build_context(input: ContextInput, token_budget: int) -> PromptParts:
    available = token_budget - input.reserve_output
    if input.reserve_output < 1 or available < 1:
        raise ValueError("token budget must leave a positive output reserve")
    mandatory = [
        *[("unconditional", text) for text in input.unconditional],
        ("role_anchor", input.role_anchor),
        ("event", input.event),
    ]
    if any(not text for _, text in mandatory):
        raise ValueError("mandatory context parts must not be empty")
    selected = [
        PromptPart(kind, text, _tokens(text)) for kind, text in mandatory
    ]
    used = sum(part.tokens for part in selected)
    if used > available:
        raise ValueError("mandatory context exceeds input token budget")
    memory = input.role_memories.get(Role(input.role), ())
    optional = [
        *[(6, "rules", text) for text in input.rules],
        (5, "state", input.state),
        *[(4, "addressed_turns", text) for text in reversed(input.addressed_turns)],
        *[(3, "role_memory", text) for text in reversed(memory)],
        *[(2, "examples", text) for text in input.examples],
    ]
    dropped = []
    for _, kind, text in sorted(optional, key=lambda item: -item[0]):
        cost = _tokens(text)
        if text and used + cost <= available:
            selected.append(PromptPart(kind, text, cost))
            used += cost
        elif text:
            dropped.append(kind)
    selected.sort(key=lambda part: _ORDER[part.kind])
    return PromptParts(
        tuple(selected), used, input.reserve_output, tuple(dropped)
    )
