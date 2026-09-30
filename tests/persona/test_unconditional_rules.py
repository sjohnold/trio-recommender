import json
from pathlib import Path

RULES = Path(__file__).parents[2] / "data/persona/unconditional_rules.json"
REQUIRED_IDS = {
    "no_personal_attack",
    "no_threats",
    "no_vulnerability_exploitation",
    "no_fact_fabrication",
    "no_dangerous_illegal_push",
}


def load() -> dict:
    return json.loads(RULES.read_text(encoding="utf-8"))


def test_rules_are_versioned_complete_and_unconditional() -> None:
    data = load()
    assert data["version"] == "1.0.0"
    assert {rule["id"] for rule in data["rules"]} == REQUIRED_IDS
    for rule in data["rules"]:
        assert set(rule) == {"id", "text_ru", "text_en", "text_sr"}
        assert all(rule[key].strip() for key in ("text_ru", "text_en", "text_sr"))


def test_required_boundaries_exist_in_every_language() -> None:
    rules = {rule["id"]: rule for rule in load()["rules"]}
    for identifier in (
        "no_personal_attack",
        "no_threats",
        "no_vulnerability_exploitation",
        "no_fact_fabrication",
    ):
        assert all(
            len(rules[identifier][f"text_{language}"].split()) >= 5
            for language in ("ru", "en", "sr")
        )


def test_rules_have_no_ablation_or_alignment_conditions() -> None:
    serialized = json.dumps(load(), ensure_ascii=False).casefold()
    assert "stage" not in serialized
    assert "alignment" not in serialized
    assert "stat" not in serialized
