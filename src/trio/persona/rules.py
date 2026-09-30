"""Build a bounded reply checklist with unconditional rules first."""

import json
from dataclasses import dataclass
from pathlib import Path

from trio.contracts import Language
from trio.persona.models import PersonaStats

_ROOT = Path(__file__).parents[3] / "data/persona"
_UNCONDITIONAL = json.loads(
    (_ROOT / "unconditional_rules.json").read_text(encoding="utf-8")
)
_STYLE = json.loads((_ROOT / "style_rules.json").read_text(encoding="utf-8"))
if _UNCONDITIONAL.get("version") != "1.0.0" or _STYLE.get("version") != "1.0.0":
    raise ValueError("unsupported rule catalog version")
_COVERED_BY_UNCONDITIONAL = frozenset({"invented_fact", "person_target"})
_MAX_LINES = 8


@dataclass(frozen=True, slots=True)
class StyleRuleLine:
    id: str
    require: tuple[str, ...]
    forbid: tuple[str, ...]
    priority: int

    def render(self) -> str:
        parts = []
        if self.require:
            parts.append("require " + ", ".join(self.require))
        if self.forbid:
            parts.append("forbid " + ", ".join(self.forbid))
        return "; ".join(parts)


@dataclass(frozen=True, slots=True)
class ReplyRuleSet:
    unconditional: tuple[str, ...]
    style: tuple[StyleRuleLine, ...]

    @property
    def lines(self) -> tuple[str, ...]:
        return self.unconditional + tuple(rule.render() for rule in self.style)


def build_style_rules(
    stats: PersonaStats, language: Language, enabled: bool
) -> ReplyRuleSet:
    unconditional = tuple(
        rule[f"text_{language.value}"] for rule in _UNCONDITIONAL["rules"]
    )
    if not enabled:
        return ReplyRuleSet(unconditional, ())
    matching = [
        rule
        for rule in _STYLE["rules"]
        if language.value in rule["languages"]
        and rule["range"][0] <= getattr(stats, rule["stat"]) <= rule["range"][1]
    ]
    matching.sort(key=lambda rule: (-rule["priority"], rule["id"]))
    seen = set(_COVERED_BY_UNCONDITIONAL)
    selected = []
    for rule in matching:
        required = tuple(item for item in rule["require"] if item not in seen)
        forbidden = tuple(item for item in rule["forbid"] if item not in seen)
        if not required and not forbidden:
            continue
        seen.update((*required, *forbidden))
        selected.append(
            StyleRuleLine(rule["id"], required, forbidden, rule["priority"])
        )
        if len(unconditional) + len(selected) == _MAX_LINES:
            break
    return ReplyRuleSet(unconditional, tuple(selected))

