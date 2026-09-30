import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCHEMA = json.loads((ROOT / "schemas/voice_example.schema.json").read_text())
ROWS = [
    json.loads(line)
    for line in (ROOT / "data/voice_bible/en.jsonl").read_text().splitlines()
]
ANCHORS = {
    "pragmatist": ("Here's the practical move:", "Let's make this concrete:"),
    "logician": ("Let's test the claim:", "The reasoning is straightforward:"),
    "empath": ("I can see why", "It matters that"),
}
STATS = set(SCHEMA["properties"]["stats"]["required"])
ALIGNMENTS = set(SCHEMA["properties"]["alignment"]["enum"])


def zone(stats: dict[str, int]) -> str:
    if max(stats.values()) >= 8:
        return "high"
    if min(stats.values()) <= 3:
        return "low"
    return "mid"


def test_en_seed_count_roles_zones_and_cells() -> None:
    assert len(ROWS) >= 18
    by_role = defaultdict(list)
    for row in ROWS:
        by_role[row["role"]].append(row)
    assert set(by_role) == set(ANCHORS)
    for role, rows in by_role.items():
        assert len(rows) >= 6
        assert {zone(row["stats"]) for row in rows} == {"low", "mid", "high"}
        assert len({row["alignment"] for row in rows}) >= 4


def test_en_seeds_follow_schema_language_anchor_and_topic_tag() -> None:
    required = set(SCHEMA["required"])
    for row in ROWS:
        assert set(row) == required
        assert row["language"] == {"language": "en", "script": "Latn", "variant": None}
        assert set(row["stats"]) == STATS
        assert all(1 <= value <= 10 for value in row["stats"].values())
        assert sum(max(value - 5, 0) for value in row["stats"].values()) <= 10
        assert row["alignment"] in ALIGNMENTS
        assert row["text"].startswith(ANCHORS[row["role"]])
        assert 20 <= len(row["text"].split()) <= 120
        assert not re.search(r"[А-Яа-яЁё]", row["text"])
        assert row["topic"] and len(row["topic"]) <= 48
        assert row["source_kind"] == "authored"
        assert row["review_status"] == "approved"
        assert row["real_person_based"] is row["machine_translated"] is False


def test_en_seeds_are_unique_and_cover_alignment_grid() -> None:
    ids = [row["id"] for row in ROWS]
    texts = [" ".join(row["text"].lower().split()) for row in ROWS]
    assert len(ids) == len(set(ids))
    assert len(texts) == len(set(texts))
    assert {row["alignment"] for row in ROWS} == ALIGNMENTS
