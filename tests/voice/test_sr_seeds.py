import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trio.language.contracts import LanguageLock
from trio.language.serbian import check_variant

SCHEMA = json.loads((ROOT / "schemas/voice_example.schema.json").read_text())
ROWS = [
    json.loads(line)
    for line in (ROOT / "data/voice_bible/sr.jsonl").read_text().splitlines()
]
LOCK = LanguageLock(language="sr", script="Latn", variant="ekavian")
ANCHORS = {
    "pragmatist": ("Hajde ovako:", "Praktično gledano,"),
    "logician": ("Proverimo tvrdnju:", "Zaključak je jednostavan:"),
    "empath": ("Razumem zašto", "Važno je da"),
}
STATS = set(SCHEMA["properties"]["stats"]["required"])
ALIGNMENTS = set(SCHEMA["properties"]["alignment"]["enum"])


def zone(stats: dict[str, int]) -> str:
    if max(stats.values()) >= 8:
        return "high"
    if min(stats.values()) <= 3:
        return "low"
    return "mid"


def test_sr_seed_count_roles_zones_and_cells() -> None:
    assert len(ROWS) >= 18
    by_role = defaultdict(list)
    for row in ROWS:
        by_role[row["role"]].append(row)
    assert set(by_role) == set(ANCHORS)
    for role, rows in by_role.items():
        assert len(rows) >= 6
        assert {zone(row["stats"]) for row in rows} == {"low", "mid", "high"}
        assert len({row["alignment"] for row in rows}) >= 4


def test_sr_seeds_follow_schema_lock_variant_and_anchor() -> None:
    required = set(SCHEMA["required"])
    for row in ROWS:
        assert set(row) == required
        assert row["language"] == {"language": "sr", "script": "Latn", "variant": "ekavian"}
        assert set(row["stats"]) == STATS
        assert all(1 <= value <= 10 for value in row["stats"].values())
        assert sum(max(value - 5, 0) for value in row["stats"].values()) <= 10
        assert row["alignment"] in ALIGNMENTS
        assert row["text"].startswith(ANCHORS[row["role"]])
        assert 20 <= len(row["text"].split()) <= 120
        assert not re.search(r"[А-Яа-яЁё]", row["text"])
        report = check_variant(row["text"], LOCK)
        assert report.mixed is False and report.conforms is True
        assert report.neighbor_score == 0
        assert row["source_kind"] == "authored"
        assert row["review_status"] == "approved"
        assert row["real_person_based"] is row["machine_translated"] is False


def test_sr_seeds_are_unique_and_cover_alignment_grid() -> None:
    ids = [row["id"] for row in ROWS]
    texts = [" ".join(row["text"].lower().split()) for row in ROWS]
    assert len(ids) == len(set(ids))
    assert len(texts) == len(set(texts))
    assert {row["alignment"] for row in ROWS} == ALIGNMENTS
