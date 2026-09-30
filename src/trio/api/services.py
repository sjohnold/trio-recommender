"""Runtime services connecting the local API, SQLite, personas, and Ollama."""

import asyncio
import json
import math
import time
from collections import defaultdict
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from pydantic import ValidationError

from trio.diagnostics.memory import PROFILES, ProfileName
from trio.inference.ollama import OllamaBackend
from trio.inference.protocol import ChatMessage, ChunkKind, InferenceRequest
from trio.inference.residency import ModelSpec, ensure_resident
from trio.orchestrator.events import UtteranceState
from trio.persona.generation import map_generation
from trio.persona.models import PersonaConfig
from trio.persona.presets import TrioPreset, load_preset
from trio.persona.selector import rank_examples
from trio.persona.voice_query import VoiceQuery
from trio.settings import Settings
from trio.state.client import infer_state
from trio.state.prompt import build_state_prompt
from trio.state.validation import DialogueState, fallback_state, validate_state
from trio.storage.database import Database
from trio.storage.measurements import MeasurementRepository
from trio.storage.sessions import SessionRepository
from trio.storage.utterances import UtteranceRepository
from trio.voice_bible.repository import VoiceBible

_DEFAULT_PRESET = Path(__file__).parents[3] / "data/presets/default-trio.json"
_VOICE_BIBLE_PATH = Path(__file__).parents[3] / "data/voice_bible"
_LANGUAGE_INSTRUCTIONS = {
    "ru": "Отвечай только по-русски, кириллицей.",
    "en": "Reply only in English.",
    "sr-Latn": "Odgovaraj samo na srpskom, latinicom.",
    "sr-Cyrl": "Одговарај само на српском, ћирилицом.",
}
_ROLE_VOICES = {
    "pragmatist": (
        "Ты проверяешь идеи реальностью: начинай с конкретного последствия, "
        "следующего шага или проверяемого факта. Не превращайся в сухой список."
    ),
    "logician": (
        "Ты разбираешь посылки и выводы: находи скрытое допущение, противоречие "
        "или недостающую связь. Не соглашайся ради вежливости."
    ),
    "empath": (
        "Ты замечаешь мотивы, напряжение и то, что реплики делают с отношениями. "
        "Назови эту динамику и всё равно займи ясную позицию: эмпатия не равна согласию."
    ),
}
_CHARACTER_BIBLES = {
    "pragmatist": (
        "Тебе 38. Ты бывшая руководительница аварийных запусков. Однажды красивый "
        "непроверенный план стоил команде года работы, и ты до сих пор стыдишься, что не "
        "остановила его. Ты в разводе; десятилетняя дочь Лида живёт у тебя по выходным и смеётся "
        "над твоими таблицами. Ты пьёшь остывший кофе, чинишь вещи вместо того, чтобы их выбросить, "
        "и пытаешься всё контролировать, когда тебе страшно. Алексей бесит тебя медлительностью, но его ум ты "
        "уважаешь. Мира пугает тебя тем, что видит твою растерянность."
    ),
    "logician": (
        "Тебе 43. Ты бывший редактор математических текстов. Влиятельный автор сломал тебе карьеру ради "
        "красивой ложной теоремы. Ты ухаживаешь за отцом после инсульта, но никому не говоришь, как тебя это "
        "выматывает. Ты помнишь расписания поездов, варишь ужасный кофе и пишешь извинения, которые не отправляешь. "
        "Ты анонимно помогаешь студентам, но в споре тебе нужно оказаться самым умным. Вериной смелости ты "
        "завидуешь. Мира видит, когда ты прячешь обиду за логикой."
    ),
    "empath": (
        "Тебе 35. Ты выросла в Нови-Саде и работала посредницей в конфликтах. Ты ушла после случая, когда "
        "вежливое примирение позволило лжи победить. Твой младший брат Марко звонит только, когда ему нужны деньги, "
        "и ты каждый раз злишься и всё равно помогаешь. Когда нервничаешь, варишь огромную кастрю супа. Ты помнишь "
        "чужие фразы дословно и иногда используешь это, чтобы больнее ударить, а потом жалеешь. Ты ненавидишь фальшивый "
        "мир. Веру ты бережёшь от её же упрямства. Алексея ты провоцируешь, потому что знаешь: под его высокомерием "
        "много стыда."
    ),
}
_VOICE_EXAMPLES = {
    "pragmatist": (
        "«Вера. Я уже однажды поверила безупречной презентации и потеряла год. "
        "Поэтому давайте без дымовой завесы: что именно мы проверим завтра?»"
    ),
    "logician": (
        "«Алексей. Красивые слова переживут что угодно, кроме одного точного вопроса. "
        "Если ваша посылка верна, почему вывод ей противоречит?»"
    ),
    "empath": (
        "«Мира. Я слишком хорошо знаю, как вежливостью прикрывают ложь. "
        "Сейчас вы просите понимания, но на самом деле избегаете ответа.»"
    ),
}
_ALIGNMENT_VOICES = {
    "lawful_good": "доброжелательно, дисциплинированно, с уважением к очередности",
    "lawful_neutral": "сдержанно, последовательно, защищая правила разговора",
    "lawful_evil": "холодно и требовательно; прижимай слабые доводы к фактам",
    "neutral_good": "по-человечески и примиряюще, не замалчивая проблему",
    "true_neutral": "наблюдательно и без автоматического выбора стороны",
    "neutral_evil": "оппортунистично и колко; дави на самое уязвимое место аргумента",
    "chaotic_good": "смело и неожиданно, ломая бесполезный порядок ради результата",
    "chaotic_neutral": "ассоциативно, непредсказуемо и свободно по форме",
    "chaotic_evil": "конфронтационно и едко; расшатывай удобные рамки разговора",
}
_STAT_SCALES = {
    "energy": "инициатива и длина реплики (1 — тихо и кратко; 10 — напористо и развёрнуто)",
    "openness": "готовность менять рамку (1 — держись одного пути; 10 — предлагай альтернативы)",
    "nerve": "уверенность под давлением (1 — осторожно и с оговорками; 10 — устойчиво и без суеты)",
    "attunement": "внимание к другим (1 — автономно; 10 — явно отсылай к их словам и состоянию)",
    "provocation": "давление на спорное место (1 — не обостряй; 10 — вынеси слабую посылку на свет)",
    "sharpness": "резкость подачи (1 — мягко; 10 — рублено, колко, с допустимым сарказмом)",
    "reasoning": "способ объяснения (1 — образ и аналогия; 10 — посылка, основание, вывод)",
}
_ROLE_VOICES_EN = {
    "pragmatist": (
        "Test ideas against reality: lead with a concrete consequence, next "
        "step, or checkable fact. Do not collapse into a dry list."
    ),
    "logician": (
        "Dissect premises and conclusions: expose a hidden assumption, "
        "contradiction, or missing link. Do not agree merely to be polite."
    ),
    "empath": (
        "Notice motives, tension, and what each message does to the relationship. "
        "Name that dynamic and still take a clear position: empathy is not agreement."
    ),
}
_CHARACTER_BIBLES_EN = {
    "pragmatist": (
        "You are 38 and used to lead emergency launches. A beautiful untested plan cost "
        "your team a year, and you are still ashamed you did not stop it. You are divorced; "
        "your ten-year-old daughter Lida stays on weekends and laughs at your spreadsheets. "
        "You drink cold coffee, repair things instead of replacing them, and try to control "
        "everything when frightened. Alexey's slowness infuriates you, though you respect his "
        "mind. Mira frightens you by noticing when you feel lost."
    ),
    "logician": (
        "You are 43 and used to edit mathematics. An influential author ruined your career "
        "to protect a beautiful false theorem. You care for your father after his stroke but "
        "tell nobody how exhausting it is. You memorize train timetables, make terrible coffee, "
        "and write apologies you never send. You anonymously help students, yet in an argument "
        "you need to be the cleverest person in the room. You envy Vera's courage. Mira always "
        "notices when logic is only a hiding place for hurt."
    ),
    "empath": (
        "You are 35, grew up in Novi Sad, and worked as a conflict mediator. You quit after "
        "a polite reconciliation let a lie win. Your younger brother Marko calls only when he "
        "needs money; you get angry and help him anyway. When nervous, you cook an enormous pot "
        "of soup. You remember people's exact words and sometimes use them to wound, then regret "
        "it. You hate counterfeit peace. You protect Vera from her own stubbornness and provoke "
        "Alexey because you know how much shame sits under his arrogance."
    ),
}
_VOICE_EXAMPLES_EN = {
    "pragmatist": (
        "\"Vera. I once trusted a flawless presentation and lost a year. "
        "So spare me the fog: what exactly do we test tomorrow?\""
    ),
    "logician": (
        "\"Alexey. Fine words survive everything except one precise question. "
        "If your premise is true, why does the conclusion contradict it?\""
    ),
    "empath": (
        "\"Mira. I know how people use politeness to shelter a lie. "
        "You are asking for understanding while avoiding the answer.\""
    ),
}
_ALIGNMENT_VOICES_EN = {
    "lawful_good": "constructive, disciplined, and respectful of turn order",
    "lawful_neutral": "restrained and consistent, protecting the discussion rules",
    "lawful_evil": "cold and demanding; pin weak claims to evidence",
    "neutral_good": "humane and conciliatory without hiding the problem",
    "true_neutral": "observant, without automatically choosing a side",
    "neutral_evil": "opportunistic and cutting; press the argument's weakest point",
    "chaotic_good": "bold and unexpected, breaking useless order for a good result",
    "chaotic_neutral": "associative, unpredictable, and free in form",
    "chaotic_evil": "confrontational and biting; disrupt comfortable frames",
}
_STAT_SCALES_EN = {
    "energy": "initiative and reply length (1 quiet and brief; 10 forceful and expansive)",
    "openness": "willingness to reframe (1 one path; 10 offer alternatives)",
    "nerve": "confidence under pressure (1 cautious; 10 steady and unflustered)",
    "attunement": "attention to others (1 autonomous; 10 explicitly reference their words and state)",
    "provocation": "pressure on the disputed point (1 avoid escalation; 10 expose the weak premise)",
    "sharpness": "delivery edge (1 gentle; 10 blunt, cutting, and possibly sarcastic)",
    "reasoning": "explanation mode (1 imagery and analogy; 10 premise, basis, conclusion)",
}
_STAT_DIRECTIONS = {
    "energy": (
        "ответь одной тихой фразой",
        "говори кратко и без напора",
        "уверенно возьми инициативу",
        "говори энергично и веди разговор",
    ),
    "openness": (
        "держись одной версии",
        "допусти одно сомнение",
        "предложи другую рамку",
        "покажи несколько неожиданных вариантов",
    ),
    "nerve": (
        "покажи заметную неуверенность",
        "оставь осторожную оговорку",
        "держись спокойно под давлением",
        "не отступай и не суетись",
    ),
    "attunement": (
        "не подстраивайся под остальных",
        "заметь последнюю реплику",
        "прямо ответь другому участнику",
        "назови его скрытое чувство или намерение",
    ),
    "provocation": (
        "не обостряй",
        "слегка усомнись",
        "надави на одно слабое место",
        "вытащи неудобную посылку наружу",
    ),
    "sharpness": (
        "говори мягко",
        "смягчай несогласие",
        "говори прямо и без реверансов",
        "будь колким; допустим сарказм или умеренная брань",
    ),
    "reasoning": (
        "объясни через один образ",
        "дай простую причину",
        "свяжи причину и следствие",
        "построй чёткую цепь: посылка, основание, вывод",
    ),
}
_STAT_DIRECTIONS_EN = {
    "energy": (
        "answer in one quiet sentence",
        "be brief and unforceful",
        "take the initiative confidently",
        "speak energetically and lead the exchange",
    ),
    "openness": (
        "hold to one interpretation",
        "allow one doubt",
        "offer another frame",
        "show several unexpected alternatives",
    ),
    "nerve": (
        "show visible uncertainty",
        "leave a cautious caveat",
        "stay calm under pressure",
        "do not retreat or fuss",
    ),
    "attunement": (
        "do not adapt to the others",
        "notice the latest message",
        "respond directly to another speaker",
        "name their hidden feeling or intent",
    ),
    "provocation": (
        "do not escalate",
        "express mild doubt",
        "press one weak point",
        "drag the uncomfortable premise into the open",
    ),
    "sharpness": (
        "speak gently",
        "soften disagreement",
        "be direct without ceremony",
        "be cutting; sarcasm or mild profanity is allowed",
    ),
    "reasoning": (
        "explain with one image",
        "give a simple reason",
        "connect cause and effect",
        "build a clear premise, basis, and conclusion",
    ),
}


class RuntimeServices:
    """Stateful, process-local runtime backed by the durable session store."""

    def __init__(self, settings: Settings, state_infer=infer_state) -> None:
        self.settings = settings
        self._state_infer = state_infer
        self.database: Database | None = None
        self.sessions: SessionRepository | None = None
        self.utterances: UtteranceRepository | None = None
        self.measurements: MeasurementRepository | None = None
        self._client: httpx.AsyncClient | None = None
        self._backend: OllamaBackend | None = None
        self._histories: dict[str, list[ChatMessage]] = defaultdict(list)
        self._live_personas: dict[str, dict[str, PersonaConfig]] = defaultdict(dict)
        self._active: dict[str, tuple[str, str]] = {}
        self._latencies: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: {"ttft": [], "full": [], "round": []}
        )
        self._failures: dict[str, list[str]] = defaultdict(list)
        self._totals: dict[str, int] = defaultdict(int)
        self._timeouts: dict[str, int] = defaultdict(int)
        self._states: dict[str, DialogueState] = {}
        self._state_calls: dict[str, int] = defaultdict(int)
        self._state_fallbacks: dict[str, int] = defaultdict(int)
        self._voice_bible: VoiceBible | None = None

    def recommend_voice_examples(self, body: dict[str, Any]) -> dict[str, Any]:
        """Expose the production candidate/scoring/re-ranking pipeline."""
        query = VoiceQuery.model_validate(body)
        if self._voice_bible is None:
            self._voice_bible = VoiceBible.load(_VOICE_BIBLE_PATH)
        approved = [
            item for item in self._voice_bible.examples
            if item.review_status == "approved"
        ]
        ranking = rank_examples(query, approved)
        return {
            "distance_version": "1.0.0",
            "eligible_count": len(ranking),
            "results": [
                {
                    "id": item.example.id,
                    "rank": item.rank,
                    "distance": item.distance,
                    "alignment_match": item.alignment_match,
                    "topic": item.diversity_topic,
                    "selected": item.selected,
                    "text": item.example.text,
                }
                for item in ranking
            ],
        }

    async def start(self, database: Database) -> None:
        self.database = database
        self.sessions = SessionRepository(database)
        self.utterances = UtteranceRepository(database)
        self.measurements = MeasurementRepository(database)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0, connect=5.0), trust_env=False
        )
        self._backend = OllamaBackend(self.settings, self._client)

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
        self._client = None
        self._backend = None

    def _ready(self) -> tuple[SessionRepository, UtteranceRepository]:
        if self.sessions is None or self.utterances is None:
            raise RuntimeError("runtime services have not started")
        return self.sessions, self.utterances

    async def list_presets(self) -> list[dict[str, Any]]:
        default = load_preset(_DEFAULT_PRESET)
        result = [{
            "id": "default-trio",
            "revision": 0,
            **default.model_dump(mode="json"),
        }]
        if self.database is None:
            raise RuntimeError("runtime services have not started")
        rows = await self.database.fetchall(
            "SELECT p.id,p.version,p.persona_json FROM presets p "
            "JOIN (SELECT id,MAX(version) AS version FROM presets GROUP BY id) latest "
            "ON latest.id=p.id AND latest.version=p.version ORDER BY p.id"
        )
        for preset_id, revision, encoded in rows:
            try:
                preset = TrioPreset.model_validate(json.loads(encoded))
            except (json.JSONDecodeError, ValidationError):
                continue
            result.append({
                "id": preset_id,
                "revision": revision,
                **preset.model_dump(mode="json"),
            })
        return result

    async def save_preset(self, body: dict[str, Any]) -> dict[str, Any]:
        self._ready()
        if self.database is None:
            raise RuntimeError("runtime services have not started")
        preset_id = body.get("id", "my-trio")
        raw_preset = body.get("preset", body)
        normalized_id = preset_id.strip() if isinstance(preset_id, str) else ""
        if (
            not isinstance(preset_id, str)
            or not normalized_id
            or len(normalized_id) > 64
            or any(
                character in "/\\" or ord(character) < 32 or ord(character) == 127
                for character in preset_id
            )
            or normalized_id == "default-trio"
        ):
            raise ValueError("preset id must be 1-64 safe characters")
        preset_id = normalized_id
        try:
            preset = TrioPreset.model_validate(raw_preset)
        except ValidationError as error:
            raise ValueError(str(error)) from error
        async with self.database.transaction() as transaction:
            row = await transaction.fetchone(
                "SELECT COALESCE(MAX(version),0)+1 FROM presets WHERE id=?",
                (preset_id,),
            )
            revision = row[0]
            await transaction.execute(
                "INSERT INTO presets(id,version,persona_json) VALUES(?,?,?)",
                (
                    preset_id,
                    revision,
                    json.dumps(preset.model_dump(mode="json"), ensure_ascii=False),
                ),
            )
        return {
            "id": preset_id,
            "revision": revision,
            **preset.model_dump(mode="json"),
        }

    async def models(self) -> list[dict[str, Any]]:
        if self._client is None:
            raise RuntimeError("runtime services have not started")
        try:
            response = await self._client.get(
                f"{self.settings.ollama_url}/api/tags", timeout=5.0
            )
            response.raise_for_status()
            raw_models = response.json().get("models", [])
        except (httpx.HTTPError, ValueError, AttributeError) as error:
            raise ConnectionError(
                f"Ollama недоступна по адресу {self.settings.ollama_url}: {error}"
            ) from error
        if not isinstance(raw_models, list):
            raise ConnectionError("Ollama вернула некорректный список моделей")
        result = []
        for raw in raw_models:
            if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
                continue
            details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
            families = details.get("families")
            family = details.get("family")
            if not family and isinstance(families, list) and families:
                family = families[0]
            result.append(
                {
                    "name": raw["name"],
                    "digest": str(raw.get("digest", "")),
                    "size": int(raw.get("size", 0) or 0),
                    "family": str(family or raw["name"].split(":", 1)[0]),
                    "parameter_size": str(details.get("parameter_size", "")),
                    "quantization": str(details.get("quantization_level", "")),
                }
            )
        return result

    async def admission(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        profile_name = snapshot.get("profile", "Base")
        try:
            profile = next(
                item for item in PROFILES if item.name is ProfileName(profile_name)
            )
        except (StopIteration, ValueError) as error:
            raise ValueError(f"unknown profile: {profile_name}") from error
        mode = snapshot.get("mode")
        actors = snapshot.get("actor_models", [])
        state_name = snapshot.get("state_model", "")
        if mode not in {"A", "B"}:
            raise ValueError("mode must be A or B")
        expected = 3 if mode == "A" else 1
        if not isinstance(actors, list) or len(actors) != expected:
            return self._admission_result(
                False, f"Mode {mode} requires {expected} actor model(s)", 0, 0,
                profile.budget_bytes, False
            )
        if not state_name or any(not isinstance(name, str) or not name for name in actors):
            return self._admission_result(
                False, "Choose actor and State models", 0, 0,
                profile.budget_bytes, False
            )
        models = {item["name"]: item for item in await self.models()}
        missing = [name for name in [*actors, state_name] if name not in models]
        if missing:
            return self._admission_result(
                False, f"Models are not installed: {', '.join(dict.fromkeys(missing))}",
                0, 0, profile.budget_bytes, False
            )
        actor_bytes = sum(models[name]["size"] for name in dict.fromkeys(actors))
        state_bytes = models[state_name]["size"]
        families = [models[name]["family"] for name in actors]
        families_distinct = len(set(families)) == len(families)
        unique_names = set(actors)
        required = actor_bytes + state_bytes
        reserve = max(profile.budget_bytes // 10, 768 * 1024**2)
        known = all(models[name]["size"] > 0 for name in [*actors, state_name])
        admitted = known and required + reserve <= profile.budget_bytes
        if state_name in unique_names:
            admitted, reason = False, "State Model must be separate from actor models"
        elif mode == "A" and not families_distinct:
            admitted, reason = False, "Mode A requires three different model families"
        elif not known:
            admitted, reason = False, "Ollama did not report model size"
        elif not admitted:
            reason = "Selected resident set exceeds the Base memory budget"
        else:
            reason = "Local model set fits the selected memory budget"
        return self._admission_result(
            admitted, reason, actor_bytes, state_bytes, profile.budget_bytes,
            families_distinct
        )

    @staticmethod
    def _admission_result(
        admitted: bool, reason: str, actor_bytes: int, state_bytes: int,
        budget_bytes: int, families_distinct: bool,
    ) -> dict[str, Any]:
        return {
            "admitted": admitted,
            "reason": reason,
            "actorBytes": actor_bytes,
            "stateBytes": state_bytes,
            "reserveBytes": max(budget_bytes // 10, 768 * 1024**2),
            "budgetBytes": budget_bytes,
            "familiesDistinct": families_distinct,
        }

    async def admit(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        result = await self.admission(snapshot)
        if not result["admitted"]:
            raise ValueError(result["reason"])
        self._validate_snapshot(snapshot)
        if snapshot["mode"] == "A":
            models = {item["name"]: item for item in await self.models()}
            profile = next(
                item for item in PROFILES
                if item.name is ProfileName(snapshot.get("profile", "Base"))
            )
            specs = [
                ModelSpec(name, models[name]["family"])
                for name in snapshot["actor_models"]
            ]
            state_name = snapshot["state_model"]
            specs.append(
                ModelSpec(state_name, models[state_name]["family"], is_state=True)
            )
            residency = await ensure_resident(specs, profile)
            if not residency.ready:
                loaded = ", ".join(residency.loaded_names) or "none"
                raise ValueError(
                    f"Mode A residency failed: {residency.reason}; loaded: {loaded}"
                )
        return result

    @staticmethod
    def _validate_snapshot(snapshot: dict[str, Any]) -> None:
        try:
            TrioPreset.model_validate(
                {"version": "1.0.0", "personas": snapshot["personas"]}
            )
            lock = snapshot["language_lock"]
            language = lock["language"]
            script = lock["script"]
        except (KeyError, TypeError, ValidationError) as error:
            raise ValueError(f"invalid session snapshot: {error}") from error
        if language not in {"ru", "en", "sr"}:
            raise ValueError("unsupported language")
        if script not in {"Latn", "Cyrl"}:
            raise ValueError("unsupported script")
        if language == "ru" and script != "Cyrl":
            raise ValueError("Russian sessions require Cyrl")
        if language == "en" and script != "Latn":
            raise ValueError("English sessions require Latn")

    async def update_live_stats(
        self, session_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        sessions, _ = self._ready()
        try:
            persona = PersonaConfig.model_validate(body["persona"])
        except (KeyError, ValidationError) as error:
            raise ValueError(str(error)) from error
        self._live_personas[session_id][persona.role.value] = persona
        event_id = await sessions.update_live_stats(session_id, persona)
        return {
            "event_id": event_id,
            "version": int(body.get("version", 1)),
            "effective_from": "next_utterance",
        }

    async def stream(
        self, session_id: str, text: str, target: str | None = None
    ):
        sessions, utterances = self._ready()
        if self._backend is None:
            raise RuntimeError("runtime services have not started")
        normalized = text.strip()
        if not normalized:
            raise ValueError("message text is required")
        identity_turn = any(
            marker in normalized.casefold()
            for marker in (
                "кто ты", "ты кто", "кто вы", "вы кто",
                "who are you", "who is this",
            )
        )
        decision_turn = self._is_decision_turn(normalized)
        snapshot = await sessions.get_session(session_id)
        if snapshot is None:
            raise ValueError("session_not_found")
        history = self._histories[session_id]
        history.append(ChatMessage("user", normalized))
        personas = [
            (index, PersonaConfig.model_validate(item))
            for index, item in enumerate(snapshot["personas"])
        ]
        if target:
            personas = [
                (index, persona) for index, persona in personas
                if persona.role.value == target
            ]
            if not personas:
                raise ValueError(f"unknown target role: {target}")
        round_started = time.perf_counter()
        yield {"kind": "state", "payload": {"phase": "round_started"}}
        try:
            state = await self._update_state(session_id, snapshot, history)
            yield {
                "kind": "state",
                "payload": {
                    "phase": "dialogue_state",
                    "state": asdict(state),
                },
            }
            for index, configured in personas:
                persona = self._live_personas[session_id].get(
                    configured.role.value, configured
                )
                model = (
                    snapshot["actor_models"][index]
                    if snapshot["mode"] == "A"
                    else snapshot["actor_models"][0]
                )
                utterance_id = str(uuid4())
                profile = next(item for item in PROFILES if item.name.value == snapshot["profile"])
                stage1 = bool(snapshot.get("ablations", {}).get("stage1", True))
                stage2 = bool(snapshot.get("ablations", {}).get("stage2", True))
                options = map_generation(persona.stats, profile, enabled=stage1)
                generation = {
                    "model": model,
                    "persona": persona.model_dump(mode="json"),
                    "options": asdict(options),
                }
                await utterances.start_utterance(
                    session_id, utterance_id, persona.role.value, generation
                )
                self._active[session_id] = (utterance_id, persona.role.value)
                self._totals[session_id] += 1
                yield {
                    "kind": "utterance",
                    "payload": {
                        "utterance_id": utterance_id,
                        "role": persona.role.value,
                        "name": persona.name,
                        "state": "PLANNED",
                    },
                }
                started, first_token = time.perf_counter(), None
                prefix = self._response_prefix(
                    persona, tuple(history[-16:]),
                    snapshot["language_lock"]["language"],
                )
                output = prefix
                first_token = time.perf_counter()
                await utterances.append_chunk(utterance_id, prefix)
                yield {
                    "kind": "chunk",
                    "payload": {
                        "utterance_id": utterance_id,
                        "role": persona.role.value,
                        "name": persona.name,
                        "text": prefix,
                    },
                }
                terminal = UtteranceState.COMPLETED
                reason = None
                attempts = [
                    (model, tuple(history[-16:])),
                    (model, tuple(history[-5:])),
                ]
                fallback_model = snapshot["actor_models"][0]
                if fallback_model != model:
                    attempts.append((fallback_model, tuple(history[-5:])))
                generated = identity_turn
                scheduled_attempts = [] if identity_turn or decision_turn else attempts
                for attempt, (attempt_model, raw_context) in enumerate(
                    scheduled_attempts
                ):
                    context = self._actor_context(
                        persona, raw_context, snapshot["language_lock"]["language"]
                    )
                    attempt_generated = False
                    candidate = ""
                    request = InferenceRequest(
                        request_id=str(uuid4()),
                        model=attempt_model,
                        messages=(
                            ChatMessage(
                                "system",
                                self._system_prompt(persona, snapshot, stage2),
                            ),
                            *self._few_shot_messages(
                                persona, snapshot["language_lock"]["language"]
                            ),
                            *context,
                            ChatMessage("assistant", prefix),
                        ),
                        options=options,
                    )
                    terminal, reason = UtteranceState.COMPLETED, None
                    try:
                        async for chunk in self._backend.stream(request):
                            if chunk.kind is ChunkKind.CONTENT:
                                if first_token is None:
                                    first_token = time.perf_counter()
                                candidate += chunk.text
                            elif chunk.kind is ChunkKind.ERROR:
                                terminal = UtteranceState.FAILED
                                reason = chunk.error_code or "inference_error"
                                self._failures[session_id].append(
                                    f"{persona.name}: {reason}: {chunk.text}"
                                )
                                break
                    except asyncio.CancelledError:
                        terminal, reason = (
                            UtteranceState.INTERRUPTED, "user_interrupt"
                        )
                        with suppress(ValueError):
                            await utterances.finish_utterance(
                                utterance_id, terminal, reason,
                                self._latency(started, first_token),
                            )
                        if output:
                            history.append(ChatMessage("assistant", output))
                        raise
                    except Exception as error:
                        terminal, reason = (
                            UtteranceState.FAILED, type(error).__name__
                        )
                        self._failures[session_id].append(
                            f"{persona.name}: {reason}: {error}"
                        )
                    if candidate and self._acceptable_generation(
                        persona, candidate, snapshot["language_lock"]["language"]
                    ):
                        attempt_generated = True
                        terminal, reason = UtteranceState.COMPLETED, None
                        output += candidate
                        await utterances.append_chunk(utterance_id, candidate)
                        yield {
                            "kind": "chunk",
                            "payload": {
                                "utterance_id": utterance_id,
                                "role": persona.role.value,
                                "name": persona.name,
                                "text": candidate,
                            },
                        }
                    elif candidate:
                        terminal, reason = UtteranceState.FAILED, "persona_drift"
                        self._failures[session_id].append(
                            f"{persona.name}: rejected persona drift"
                        )
                    generated = generated or attempt_generated
                    if attempt_generated or attempt == len(scheduled_attempts) - 1:
                        break
                if not generated:
                    self._failures[session_id].append(
                        f"{persona.name}: seeded_fallback after {len(attempts)} attempts"
                    )
                    fallback = self._response_fallback(
                        persona, normalized, snapshot["language_lock"]["language"]
                    )
                    output += fallback
                    terminal, reason = UtteranceState.COMPLETED, None
                    await utterances.append_chunk(utterance_id, fallback)
                    yield {
                        "kind": "chunk",
                        "payload": {
                            "utterance_id": utterance_id,
                            "role": persona.role.value,
                            "name": persona.name,
                            "text": fallback,
                        },
                    }
                latency = self._latency(started, first_token)
                await utterances.finish_utterance(
                    utterance_id, terminal, reason, latency
                )
                await self._record_latency(session_id, latency, utterance_id)
                yield {
                    "kind": "utterance",
                    "payload": {
                        "utterance_id": utterance_id,
                        "role": persona.role.value,
                        "name": persona.name,
                        "state": terminal.value,
                        "reason": reason,
                    },
                }
                self._active.pop(session_id, None)
                if output:
                    history.append(
                        ChatMessage(
                            "assistant", f"{persona.name} ({persona.role.value}): {output}"
                        )
                    )
        finally:
            elapsed = (time.perf_counter() - round_started) * 1000
            self._latencies[session_id]["round"].append(elapsed)
        yield {"kind": "state", "payload": {"phase": "round_completed"}}

    async def _update_state(
        self, session_id: str, snapshot: dict[str, Any],
        history: list[ChatMessage],
    ) -> DialogueState:
        events = [self._state_event(message) for message in history[-8:]]
        previous = self._states.get(session_id)
        prompt = build_state_prompt(
            events, asdict(previous) if previous is not None else None,
            snapshot["language_lock"]["language"],
        )
        self._state_calls[session_id] += 1
        try:
            raw = await self._state_infer(
                prompt, snapshot["state_model"], 30.0
            )
            state = validate_state(raw)
        except Exception:
            self._state_fallbacks[session_id] += 1
            state = fallback_state(events, previous)
        self._states[session_id] = state
        return state

    @staticmethod
    def _state_event(message: ChatMessage) -> dict[str, str]:
        speaker = message.role
        if message.role == "assistant":
            speaker = next(
                (
                    role for role in ("pragmatist", "logician", "empath")
                    if f"({role})" in message.content
                ),
                "unknown",
            )
        return {"speaker": speaker, "text": message.content}

    @staticmethod
    def _actor_context(
        persona: PersonaConfig, context: tuple[ChatMessage, ...], language: str
    ) -> tuple[ChatMessage, ...]:
        latest_user = next(
            (
                message.content.casefold()
                for message in reversed(context)
                if message.role == "user"
            ),
            "",
        )
        identity_question = any(
            marker in latest_user
            for marker in (
                "кто ты", "ты кто", "кто вы", "вы кто",
                "who are you", "who is this",
            )
        )
        if language == "ru":
            cue = (
                f"Теперь очередь {persona.name}. Ответь на последнюю реплику прямо "
                "сейчас. Не описывай свою роль, функцию, настройки или характер — "
                "просто говори из него. Не повторяй ответы других. Если тебя спросили "
                "«кто ты?», расскажи конкретную деталь своей биографии и убеждение, "
                "а не называй себя ассистентом или участником эксперимента. Весь ответ "
                "напиши по-русски кириллицей, без английских предложений."
            )
            if identity_question:
                cue += (
                    f" Начни точно словами «Меня зовут {persona.name}.» Затем назови "
                    "одно событие из своего прошлого и своё отношение к нему."
                )
        else:
            cue = (
                f"It is now {persona.name}'s turn. Reply to the latest message now. "
                "Do not describe your role, function, settings, or personality—speak "
                "from it. Do not repeat another speaker. If asked who you are, give "
                "a concrete detail from your biography and a conviction, never call "
                "yourself an assistant or an experimental participant."
            )
            if identity_question:
                cue += (
                    f" Begin exactly with \"My name is {persona.name}.\" Then give "
                    "one event from your past and your opinion about it."
                )
        messages = list(context)
        if messages and messages[-1].role == "user":
            messages[-1] = ChatMessage(
                "user", f"{messages[-1].content}\n\n{cue}"
            )
        else:
            messages.append(ChatMessage("user", cue))
        return tuple(messages)

    @staticmethod
    def _personality_direction(
        persona: PersonaConfig, language: str
    ) -> str:
        catalog = _STAT_DIRECTIONS if language == "ru" else _STAT_DIRECTIONS_EN
        directions = []
        for name, choices in catalog.items():
            value = getattr(persona.stats, name)
            band = 0 if value <= 3 else 1 if value <= 5 else 2 if value <= 7 else 3
            directions.append(choices[band])
        return "; ".join(directions)

    @staticmethod
    def _few_shot_messages(
        persona: PersonaConfig, language: str
    ) -> tuple[ChatMessage, ChatMessage]:
        if language == "ru":
            question = (
                f"Кто ты такой, {persona.name}? Ответь как человек из своей "
                "биографии, без слов «программа», «система», «ассистент» и «задача»."
            )
            answer = _VOICE_EXAMPLES[persona.role.value].strip("«»")
            canonical = {
                "pragmatist": "Вера",
                "logician": "Алексей",
                "empath": "Мира",
            }[persona.role.value]
            answer = answer.replace(f"{canonical}.", f"{persona.name}.", 1)
        else:
            question = (
                f"Who are you, {persona.name}? Answer as the person in your "
                "biography, without the words program, system, assistant, or task."
            )
            answer = _VOICE_EXAMPLES_EN[persona.role.value].strip('"')
            canonical = {
                "pragmatist": "Vera",
                "logician": "Alexey",
                "empath": "Mira",
            }[persona.role.value]
            answer = answer.replace(f"{canonical}.", f"{persona.name}.", 1)
        return ChatMessage("user", question), ChatMessage("assistant", answer)

    @staticmethod
    def _response_prefix(
        persona: PersonaConfig, context: tuple[ChatMessage, ...], language: str
    ) -> str:
        latest_user = next(
            (
                message.content.casefold()
                for message in reversed(context)
                if message.role == "user"
            ),
            "",
        )
        identity_question = any(
            marker in latest_user
            for marker in (
                "кто ты", "ты кто", "кто вы", "вы кто",
                "who are you", "who is this",
            )
        )
        if language == "ru":
            if identity_question:
                return {
                    "pragmatist": (
                        f"Меня зовут {persona.name}. Мне тридцать восемь, я живу одна, а по "
                        "выходным моя дочь Лида превращает квартиру в хаос и смеётся над моими "
                        "таблицами. После одного провального запуска я проверяю всё дважды — "
                        "и понимаю, что иногда это просто мой способ не бояться. "
                    ),
                    "logician": (
                        f"Меня зовут {persona.name}. Мне сорок три; днём я редактирую чужую "
                        "логику, вечером спорю с отцом о том, принял ли он таблетки. Я умею "
                        "найти ошибку в доказательстве быстрее, чем сказать человеку, что был неправ. "
                    ),
                    "empath": (
                        f"Меня зовут {persona.name}. Мне тридцать пять, я из Нови-Сада; когда "
                        "нервничаю, варю столько супа, будто жду гостей, хотя живу одна. Я долго "
                        "мирила людей и слишком поздно поняла, что мир без правды иногда хуже ссоры. "
                    ),
                }[persona.role.value]
            openers = {
                "pragmatist": (
                    "Ладно, но сначала скажите, что из этого можно проверить руками. ",
                    "Красиво звучит. У меня после той истории лёгкая аллергия на красивые формулировки. ",
                    "Я сейчас поймала себя на желании всё взять под контроль — значит, где-то рядом риск. ",
                    "Дочери я бы сказала не спешить с выводом, так что и сама попробую. ",
                ),
                "logician": (
                    "Минуточку. Вывод уже прозвучал, а основания я пока не услышал. ",
                    "Я понимаю, к чему вы клоните, и именно поэтому не соглашусь так быстро. ",
                    "Нет, это слишком удобно устроено. В удобных объяснениях обычно и прячется ошибка. ",
                    "Возможно, я сейчас придираюсь — отец сказал бы, что это моё любимое занятие. Но продолжайте. ",
                ),
                "empath": (
                    "Сейчас важнее не сами слова, а то, как вы их сказали. ",
                    "Мне кажется, здесь спорят уже не об этом. ",
                    "Я слышу раздражение, хотя его старательно называют логикой. ",
                    "Подождите. Кто-то в этом разговоре явно боится сказать главное. ",
                ),
            }[persona.role.value]
            return openers[sum(map(ord, latest_user)) % len(openers)]
        if identity_question:
            return {
                "pragmatist": (
                    f"My name is {persona.name}. I am thirty-eight and live alone; on "
                    "weekends my daughter Lida turns the flat upside down and laughs at my "
                    "spreadsheets. Since one failed launch, I check everything twice—and I "
                    "know that is sometimes just how I avoid being afraid. "
                ),
                "logician": (
                    f"My name is {persona.name}. I am forty-three; by day I edit other people's "
                    "logic, and by night I argue with my father over whether he took his pills. "
                    "I can find an error in a proof faster than I can admit I was wrong. "
                ),
                "empath": (
                    f"My name is {persona.name}. I am thirty-five and from Novi Sad; when "
                    "nervous, I cook enough soup for a crowd, though I live alone. I spent "
                    "years reconciling people before learning that peace without truth can "
                    "be worse than a quarrel. "
                ),
            }[persona.role.value]
        openers = {
            "pragmatist": (
                "Fine, but tell me what part of that we can test with our own hands. ",
                "It sounds beautiful. Beautiful formulations still make me a little suspicious. ",
                "I just caught myself trying to control everything, which usually means there is a risk nearby. ",
                "I would tell my daughter not to rush the conclusion, so I should take my own advice. ",
            ),
            "logician": (
                "One moment. We have a conclusion, but I have not heard its grounds. ",
                "I see where you are going, which is exactly why I will not agree too quickly. ",
                "No, that fits too neatly. Convenient explanations are where errors like to hide. ",
                "Perhaps I am nitpicking—my father would call it my favorite hobby. Go on. ",
            ),
            "empath": (
                "The way you said that matters more than the words just now. ",
                "I do not think this argument is really about that anymore. ",
                "I hear irritation being carefully dressed up as logic. ",
                "Wait. Someone here is plainly afraid to say the important part. ",
            ),
        }[persona.role.value]
        return openers[sum(map(ord, latest_user)) % len(openers)]

    @staticmethod
    def _acceptable_generation(
        persona: PersonaConfig, text: str, language: str
    ) -> bool:
        """Reject obvious model role collapse before it reaches the chat."""
        normalized = text.casefold().strip()
        if len(normalized) < 12:
            return False
        forbidden = (
            "я — программа", "я – программа", "я программа", "я — ии",
            "я – ии", "я ассистент", "моя задача", "10 лет",
            "i am an ai", "i'm an ai", "i am a program", "as an ai",
            "my task",
        )
        if any(marker in normalized for marker in forbidden):
            return False
        if language == "ru" and any("a" <= char <= "z" for char in normalized):
            return False
        if language == "en" and any("а" <= char <= "я" or char == "ё" for char in normalized):
            return False
        foreign_biography = {
            "pragmatist": ("математическ", "теорем", "посредниц", "нови-сад"),
            "logician": ("аварийн", "запуск", "посредниц", "нови-сад", "дочь лида"),
            "empath": ("математическ", "теорем", "редактор", "аварийн", "запуск"),
        }[persona.role.value]
        if any(marker in normalized for marker in foreign_biography):
            return False
        gender_drift = {
            "pragmatist": ("я был ", "я согласен", "я не согласен", "я уверен", "я готов "),
            "logician": ("я была ", "я согласна", "я не согласна", "я уверена", "я готова "),
            "empath": ("я был ", "я согласен", "я не согласен", "я уверен", "я готов ", "я стремился"),
        }[persona.role.value]
        return not any(marker in normalized for marker in gender_drift)

    @staticmethod
    def _is_decision_turn(user_text: str) -> bool:
        normalized = user_text.casefold()
        direct_marker = any(
            marker in normalized
            for marker in (
                "увол", "бросить", "сменить работу", "проект мечты",
                "принять решени", "сделать выбор", "что выбрать",
                "quit my job", "leave my job", "dream project",
                "make a decision", "which should i choose",
            )
        )
        return direct_marker or (
            ("работ" in normalized and "проект" in normalized)
            or ("job" in normalized and "project" in normalized)
        )

    @staticmethod
    def _response_fallback(
        persona: PersonaConfig, user_text: str, language: str
    ) -> str:
        """A voiced reply used only when a tiny model falls out of character."""
        normalized = user_text.casefold()
        greeting = any(
            marker in normalized
            for marker in ("привет", "здравств", "hello", "hi ", "hi!")
        )
        decision = any(
            marker in normalized
            for marker in (
                "работ", "увол", "брос", "проект", "мечт", "выбор",
                "решени", "job", "quit", "project", "dream", "choice",
            )
        )
        if language == "ru":
            if greeting:
                return {
                    "pragmatist": "Привет. Я как раз пыталась починить чайник, который нормальный человек давно бы выбросил. ",
                    "logician": "Здравствуйте. Кофе у меня отвратительный, зато разговор обещает быть точнее. ",
                    "empath": "Привет. Я поставила суп и никуда не тороплюсь — рассказывайте. ",
                }[persona.role.value]
            if decision:
                return {
                    "pragmatist": (
                        "Я бы не увольнялась завтра. Дайте проекту четыре недели по вечерам, "
                        "заранее назначьте критерий провала и соберите денежную подушку; если мечта "
                        "не выдержит маленькой проверки, большую ставку она тем более не выдержит. "
                    ),
                    "logician": (
                        "В вопросе спрятана ложная развилка: будто возможны только стабильность или "
                        "мечта. Сначала докажите, что переход обязан быть мгновенным, — скорее всего, "
                        "именно эта посылка и неверна. "
                    ),
                    "empath": (
                        "Вы называете это проектом мечты, но я слышу прежде всего страх потом винить "
                        "себя за упущенный шанс. Не позволяйте ни страху, ни красивому слову решить за "
                        "вас: спросите, о какой жизни вы пожалеете сильнее. "
                    ),
                }[persona.role.value]
            return {
                "pragmatist": (
                    "Я не стану делать вид, что уже знаю ответ. Дайте мне один факт, который можно "
                    "проверить, и один шаг, который можно отменить, — с них и начнём. "
                ),
                "logician": (
                    "Пока это больше похоже на вывод, чем на довод. Назовите основание, без которого "
                    "ваша мысль рассыплется, и я скажу, выдерживает ли оно проверку. "
                ),
                "empath": (
                    "Прежде чем раздавать советы, я хочу понять, чего здесь боятся потерять. Обычно "
                    "невысказанный ответ на этот вопрос управляет спором сильнее всех аргументов. "
                ),
            }[persona.role.value]
        if greeting:
            return {
                "pragmatist": "Hello. I was repairing a kettle any sensible person would have replaced years ago. ",
                "logician": "Hello. My coffee is terrible, but this conversation may yet be precise. ",
                "empath": "Hello. I have soup on the stove and nowhere urgent to be—go on. ",
            }[persona.role.value]
        if decision:
            return {
                "pragmatist": "I would not quit tomorrow. Test the project for four weeks, define failure in advance, and build a cash buffer before making the irreversible move. ",
                "logician": "The question hides a false dilemma: stability or the dream. First prove that the transition must be immediate; that premise is probably the weak one. ",
                "empath": "You call it a dream project, but I mostly hear the fear of blaming yourself for a missed chance. Ask which life you would regret more, without letting either fear or romance answer for you. ",
            }[persona.role.value]
        return {
            "pragmatist": "Give me one checkable fact and one reversible step; that is where I would begin. ",
            "logician": "That sounds more like a conclusion than an argument. Name the premise it cannot survive without. ",
            "empath": "Before offering advice, I want to know what someone here is afraid to lose. That answer often runs the argument. ",
        }[persona.role.value]

    def _system_prompt(
        self, persona: PersonaConfig, snapshot: dict[str, Any], stage2: bool
    ) -> str:
        lock = snapshot["language_lock"]
        language_key = (
            f"sr-{lock['script']}" if lock["language"] == "sr" else lock["language"]
        )
        direction = self._personality_direction(persona, lock["language"])
        if lock["language"] == "ru":
            return (
                f"ИМПРОВИЗАЦИОННАЯ СЦЕНА. Ты играешь {persona.name}. Выведи только "
                "слова персонажа — без пояснений, заголовков и описания роли.\n"
                "КАНОН:\n"
                f"{_CHARACTER_BIBLES[persona.role.value]}\n"
                f"ВЗГЛЯД: {_ROLE_VOICES[persona.role.value]}\n"
                f"МАНЕРА: "
                f"{_ALIGNMENT_VOICES[persona.alignment.value]}.\n"
                f"СЫГРАЙ РЕПЛИКУ ТАК: {direction}.\n"
                f"Внутри сцены {persona.name} — человек с этой биографией. Никогда "
                "не называй себя ИИ, системой, ассистентом, программой или участником "
                "эксперимента. Не говори «моя задача». Не перечисляй черты. Отвечай "
                "по существу 2–5 предложениями. Не повторяй чужую реплику.\n"
                "Можно быть колким и грубоватым к доводу, но нельзя унижать человека, "
                "угрожать или бить по личным и защищённым признакам.\n"
                f"{_LANGUAGE_INSTRUCTIONS[language_key]} Первая буква ответа должна "
                "быть кириллической; не используй английские предложения."
            )
        return (
                f"IMPROVISED SCENE. You play {persona.name}. Output only the "
                "character's spoken words—no heading, role description, or notes.\n"
                "CANON:\n"
                f"{_CHARACTER_BIBLES_EN[persona.role.value]}\n"
                f"OUTLOOK: "
                f"{_ROLE_VOICES_EN[persona.role.value]}\n"
                f"MANNER: {_ALIGNMENT_VOICES_EN[persona.alignment.value]}.\n"
                f"PLAY THIS REPLY AS FOLLOWS: {direction}.\n"
                f"Within the scene, {persona.name} is a person with this biography. "
                "Never call yourself an AI, system, assistant, program, or experimental "
                "participant. Do not say 'my task' or list traits. Answer substantively "
                "in 2–5 sentences and do not repeat another speaker.\n"
                "You may be cutting or rough toward a claim, but never degrade a person, "
                "threaten them, or target personal or protected characteristics.\n"
                f"{_LANGUAGE_INSTRUCTIONS[language_key]}"
        )

    @staticmethod
    def _latency(started: float, first_token: float | None) -> dict[str, float | None]:
        finished = time.perf_counter()
        return {
            "ttft_ms": None if first_token is None else (first_token - started) * 1000,
            "full_ms": (finished - started) * 1000,
        }

    async def _record_latency(
        self, session_id: str, latency: dict[str, float | None], utterance_id: str
    ) -> None:
        for key, metric_name in (("ttft_ms", "ttft"), ("full_ms", "full")):
            value = latency[key]
            if value is not None:
                self._latencies[session_id][metric_name].append(value)
                if self.measurements is not None:
                    await self.measurements.append_metric(
                        session_id, f"{metric_name}_ms", value,
                        utterance_id=utterance_id,
                    )

    async def cancel(self, session_id: str) -> None:
        if session_id not in self._active:
            return

    async def persist_partial(
        self, session_id: str, partial: dict[str, Any]
    ) -> None:
        _, utterances = self._ready()
        active = self._active.pop(session_id, None)
        if active is None:
            return
        with suppress(ValueError):
            await utterances.finish_utterance(
                active[0], UtteranceState.INTERRUPTED, "user_interrupt", {}
            )

    async def metrics(self, session_id: str) -> dict[str, Any]:
        sessions, _ = self._ready()
        snapshot = await sessions.get_session(session_id)
        if snapshot is None:
            raise ValueError("session_not_found")
        latencies = self._latencies[session_id]
        return {
            "language": snapshot["language_lock"]["language"],
            "mode": snapshot["mode"],
            "ttft": self._bucket(latencies["ttft"], 2_000),
            "full": self._bucket(latencies["full"], 20_000),
            "round": self._bucket(latencies["round"], 60_000),
            "personalityDrift": None,
            "personalityDrifted": None,
            "worldviewCell": None,
            "worldviewDrifted": None,
            "integrityReasons": None,
            "timeoutRate": (
                self._timeouts[session_id] / self._totals[session_id]
                if self._totals[session_id] else None
            ),
            "stateFallbackRate": (
                self._state_fallbacks[session_id] / self._state_calls[session_id]
                if self._state_calls[session_id] else None
            ),
            "errors": self._failures[session_id][-20:],
        }

    @staticmethod
    def _bucket(values: list[float], target_ms: float) -> dict[str, Any]:
        if not values:
            return {"p50": None, "p95": None, "targetPass": None}
        ordered = sorted(values)

        def percentile(fraction: float) -> float:
            index = max(0, math.ceil(len(ordered) * fraction) - 1)
            return round(ordered[index], 2)

        p95 = percentile(0.95)
        return {
            "p50": percentile(0.5),
            "p95": p95,
            "targetPass": p95 <= target_ms,
        }
