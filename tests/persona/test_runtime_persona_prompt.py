import json
from pathlib import Path

from trio.api.services import RuntimeServices
from trio.inference.protocol import ChatMessage, ChunkKind, TokenChunk
from trio.persona.models import PersonaConfig
from trio.settings import Settings
from trio.state.client import RawStateResult
from trio.storage import database as database_module
from trio.storage.database import Database


def persona() -> PersonaConfig:
    return PersonaConfig.model_validate({
        "name": "Resonance",
        "role": "empath",
        "alignment": "neutral_good",
        "stats": {
            "energy": 6,
            "openness": 7,
            "nerve": 6,
            "sharpness": 3,
            "reasoning": 5,
            "provocation": 3,
            "attunement": 10,
        },
    })


def test_prompt_turns_every_stat_and_role_identity_into_playable_direction() -> None:
    snapshot = {
        "language_lock": {
            "language": "ru", "script": "Cyrl", "variant": None,
        },
    }
    prompt = RuntimeServices(Settings())._system_prompt(
        persona(), snapshot, stage2=True
    )

    assert "эмпатия не равна согласию" in prompt
    for direction in (
        "уверенно возьми инициативу",
        "предложи другую рамку",
        "держись спокойно под давлением",
        "назови его скрытое чувство или намерение",
        "не обостряй",
        "говори мягко",
        "дай простую причину",
    ):
        assert direction in prompt
    assert "выросла в Нови-Саде" in prompt
    assert "младший брат Марко" in prompt
    assert "не называй себя ИИ" in prompt
    few_shot = RuntimeServices._few_shot_messages(persona(), "ru")
    assert few_shot[0].role == "user"
    assert few_shot[1].role == "assistant"
    assert few_shot[1].content.startswith("Resonance.")
    prefix = RuntimeServices._response_prefix(
        persona(), (ChatMessage("user", "Вы кто такие?"),), "ru"
    )
    assert prefix.startswith("Меня зовут Resonance.")
    assert "варю столько супа" in prefix
    assert "говори из него" in RuntimeServices._actor_context(
        persona(), (), "ru"
    )[-1].content


def test_non_russian_prompt_keeps_instruction_language_coherent() -> None:
    snapshot = {
        "language_lock": {
            "language": "en", "script": "Latn", "variant": None,
        },
    }
    prompt = RuntimeServices(Settings())._system_prompt(
        persona(), snapshot, stage2=True
    )

    assert "grew up in Novi Sad" in prompt
    assert "younger brother Marko" in prompt
    assert "speak gently" in prompt
    assert RuntimeServices._few_shot_messages(
        persona(), "en"
    )[1].content.startswith("Resonance.")
    assert "Reply only in English" in prompt
    assert "посредником" not in prompt


class EmptyAssignedModels:
    def __init__(self) -> None:
        self.models = []

    async def stream(self, request):
        self.models.append(request.model)
        if request.model != "good":
            yield TokenChunk(request.request_id, ChunkKind.DONE, "{}")
            return
        yield TokenChunk(
            request.request_id, ChunkKind.CONTENT, "Проверенный ответ модели."
        )
        yield TokenChunk(request.request_id, ChunkKind.DONE, "{}")


async def state_infer(prompt, model, timeout):
    return RawStateResult(json.dumps({
        "tension": "unknown",
        "trend": "unknown",
        "relations": [],
        "topic_shift": {"detected": "unknown", "confidence": 0},
        "user_signal": {
            "valence": "unknown",
            "arousal": "unknown",
            "stance": "unknown",
            "confidence": 0,
        },
        "suggested_next": "unknown",
    }), (), 1)


async def test_empty_assigned_models_fall_back_without_cancelling_the_round(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(database_module, "aiosqlite", None)
    preset = json.loads(
        (Path(__file__).parents[2] / "data/presets/default-trio.json").read_text()
    )
    snapshot = {
        "mode": "A",
        "actor_models": ["good", "empty-logician", "empty-empath"],
        "state_model": "state",
        "model_digests": {
            "good": "g",
            "empty-logician": "l",
            "empty-empath": "e",
            "state": "s",
        },
        "profile": "Base",
        "language_lock": {
            "language": "ru", "script": "Cyrl", "variant": None,
        },
        "ablations": {"stage1": True, "stage2": True, "stage3": True},
        "personas": preset["personas"],
    }
    services = RuntimeServices(
        Settings(database_path=tmp_path / "trio.db"),
        state_infer=state_infer,
    )
    async with Database.open(tmp_path / "trio.db") as database:
        await services.start(database)
        backend = EmptyAssignedModels()
        services._backend = backend
        try:
            session_id = await services.sessions.create_session(snapshot)
            identity_events = [
                event async for event in
                services.stream(session_id, "Вы кто такие?")
            ]
            assert backend.models == []
            events = [
                event async for event in services.stream(session_id, "Hello")
            ]
        finally:
            await services.stop()

    completed = [
        event for event in events
        if event["kind"] == "utterance"
        and event["payload"].get("state") == "COMPLETED"
    ]
    assert backend.models == [
        "good",
        "empty-logician", "empty-logician", "good",
        "empty-empath", "empty-empath", "good",
    ]
    assert [event["payload"]["role"] for event in completed] == [
        "pragmatist", "logician", "empath",
    ]
    identity_chunks = [
        event["payload"] for event in identity_events
        if event["kind"] == "chunk"
    ]
    assert [payload["role"] for payload in identity_chunks] == [
        "pragmatist", "logician", "empath",
    ]
    assert all(
        payload["text"].startswith("Меня зовут")
        for payload in identity_chunks
    )


def test_generation_guard_rejects_language_and_biography_bleed() -> None:
    empath = persona()
    assert not RuntimeServices._acceptable_generation(
        empath, "Я был редактором математических текстов.", "ru"
    )
    assert not RuntimeServices._acceptable_generation(
        empath, "Я слышу ваше irritation и сомнение.", "ru"
    )
    assert RuntimeServices._acceptable_generation(
        empath, "Я слышу, как вы стараетесь скрыть сомнение за уверенностью.", "ru"
    )
