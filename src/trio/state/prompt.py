"""Bounded, localized prompt construction for the State Model."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

MAX_PROMPT_CHARS = 9_000
MAX_OUTPUT_TOKENS = 400
_SCHEMA_PATH = Path(__file__).parents[3] / "schemas/dialogue_state.schema.json"
_SYSTEM = {
    "ru": "Trio State Model: извлечение наблюдаемого состояния в JSON.",
    "en": "Trio State Model: observable state extraction as JSON.",
    "sr": "Trio State Model: izdvajanje vidljivog stanja u JSON formatu.",
}
_INSTRUCTIONS = {
    "ru": (
        "Оцени только наблюдаемые сигналы последних реплик: напряжение, его "
        "тренд, явное согласие или несогласие, связи и смену темы. Не ставь "
        "диагнозов и не приписывай скрытых намерений. Для любого неоднозначного "
        "поля обязательно используй unknown. Явное «согласен» означает stance=agree; "
        "явное «нет/неверно» — stance=disagree; информационный вопрос — neutral. "
        "trend=rising только при явном усилении конфликта, stable при продолжении "
        "без изменения, falling при явном снижении; иначе unknown. "
        "topic_shift=true для явно нового вопроса или темы, false для явного "
        "продолжения текущей темы; иначе unknown. Верни только JSON по схеме."
    ),
    "en": (
        "Assess only observable signals in the recent messages: tension, its "
        "trend, explicit agreement or disagreement, relations, and topic shift. "
        "Do not diagnose or infer hidden intentions. Use unknown for every "
        "ambiguous field. Explicit 'agree' means stance=agree; explicit "
        "'no/wrong' means stance=disagree; an informational question is neutral. "
        "Use trend=rising only for explicit escalation, stable for a continuation "
        "with no change, and falling for explicit de-escalation; otherwise unknown. "
        "Use topic_shift=true for an explicitly new question or topic and false "
        "for a clear continuation; otherwise unknown. Return only JSON matching "
        "the schema."
    ),
    "sr": (
        "Proceni samo vidljive signale u poslednjim porukama: napetost, njen "
        "trend, jasno slaganje ili neslaganje, odnose i promenu teme. Ne postavljaj "
        "dijagnoze i ne pripisuj skrivene namere. Za svako nejasno polje obavezno "
        "upiši unknown. Jasno „slažem se” znači stance=agree; jasno „ne/netačno” "
        "znači stance=disagree; informativno pitanje je neutral. trend=rising "
        "koristi samo za jasno pojačavanje sukoba, stable za nastavak bez promene, "
        "a falling za jasno smirivanje; inače unknown. topic_shift=true označava "
        "izričito novo pitanje ili temu, false jasan nastavak; inače unknown. "
        "Vrati samo JSON koji odgovara šemi."
    ),
}


@dataclass(frozen=True, slots=True)
class StatePrompt:
    system: str
    user: str
    schema: dict[str, Any]
    max_output_tokens: int = MAX_OUTPUT_TOKENS


def _bounded_json(value: object, limit: int) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(encoded) <= limit:
        return encoded
    tail = encoded[-(limit - 40):]
    return json.dumps({"truncated": True, "raw_tail": tail}, ensure_ascii=False)


def build_state_prompt(
    recent_events: Iterable[object],
    previous_state: object | None,
    language: str,
) -> StatePrompt:
    if language not in _INSTRUCTIONS:
        raise ValueError(f"unsupported prompt language: {language}")
    schema = json.loads(_SCHEMA_PATH.read_text())
    events = list(recent_events)[-8:]
    user = "\n".join((
        _INSTRUCTIONS[language],
        f"SCHEMA={json.dumps(schema, ensure_ascii=False, separators=(',', ':'))}",
        f"PREVIOUS_STATE={_bounded_json(previous_state, 1_200)}",
        f"RECENT_EVENTS={_bounded_json(events, 3_500)}",
    ))
    if len(user) > MAX_PROMPT_CHARS:
        raise ValueError("state prompt exceeds internal character budget")
    return StatePrompt(
        system=_SYSTEM[language],
        user=user,
        schema=schema,
    )
