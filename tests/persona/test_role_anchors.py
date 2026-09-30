import json
import re
from pathlib import Path

ANCHORS = Path(__file__).parents[2] / "data/persona/role_anchors.json"
TYPES = {
    "pragmatist": "fact",
    "logician": "why_or_what_if",
    "empath": "atmosphere_state",
}
SAMPLES = {
    ("pragmatist", "ru"): "На практике это работает.",
    ("pragmatist", "en"): "In practice this works.",
    ("pragmatist", "sr"): "U praksi ovo radi.",
    ("logician", "ru"): "Что если условие ложно?",
    ("logician", "en"): "What if the premise is false?",
    ("logician", "sr"): "Šta ako je pretpostavka pogrešna?",
    ("empath", "ru"): "По тону реплик разговор ускорился.",
    ("empath", "en"): "From the replies, the exchange sped up.",
    ("empath", "sr"): "Iz replika se vidi da je razgovor ubrzan.",
}


def load() -> dict:
    return json.loads(ANCHORS.read_text(encoding="utf-8"))


def test_every_role_and_language_has_multiple_regex_anchors() -> None:
    data = load()
    assert data["version"] == "1.0.0"
    assert {role: item["type"] for role, item in data["roles"].items()} == TYPES
    for item in data["roles"].values():
        assert set(item["patterns"]) == {"ru", "en", "sr"}
        for patterns in item["patterns"].values():
            assert len(patterns) >= 2
            assert all(pattern.startswith("^") for pattern in patterns)
            for pattern in patterns:
                re.compile(pattern)


def test_representative_openings_are_machine_checkable() -> None:
    roles = load()["roles"]
    for (role, language), sample in SAMPLES.items():
        assert any(
            re.search(pattern, sample.casefold())
            for pattern in roles[role]["patterns"][language]
        )


def test_serbian_anchors_do_not_mix_script() -> None:
    serialized = json.dumps(
        {role: item["patterns"]["sr"] for role, item in load()["roles"].items()},
        ensure_ascii=False,
    )
    assert not re.search(r"[\u0400-\u04ff]", serialized)
