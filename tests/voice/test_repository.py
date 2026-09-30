import json
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trio.language.contracts import LanguageLock
from trio.persona.models import PersonaStats
from trio.persona.voice_query import VoiceQuery
from trio.voice_bible.repository import VoiceBible, VoiceBibleValidationError
def query() -> VoiceQuery:
    return VoiceQuery(
        language=LanguageLock(language="ru", script="Cyrl", variant=None),
        role="pragmatist",
        stats=PersonaStats(
            energy=5, openness=5, nerve=5, sharpness=5,
            reasoning=5, provocation=5, attunement=5,
        ),
        alignment="lawful_good",
        limit=2,
    )
def test_loads_all_languages_deterministically_and_queries() -> None:
    path = ROOT / "data/voice_bible"
    first = VoiceBible.load(path)
    second = VoiceBible.load(path)
    assert len(first.examples) == 54
    assert [item.id for item in first.examples] == [item.id for item in second.examples]
    selected = first.query(query())
    assert len(selected) == 2
    assert all(item.language.language.value == "ru" for item in selected)
def test_unapproved_rows_are_excluded(tmp_path: Path) -> None:
    row = json.loads((ROOT / "data/voice_bible/ru.jsonl").read_text().splitlines()[0])
    rows = []
    for index, status in enumerate(("approved", "approved", "draft"), 1):
        item = dict(row, id=f"temporary-{index}", review_status=status)
        item["text"] = row["text"] + f" Дополнение номер {index}."
        rows.append(item)
    (tmp_path / "ru.jsonl").write_text("\n".join(map(json.dumps, rows)))
    assert all(item.review_status == "approved" for item in VoiceBible.load(tmp_path).query(query()))
def test_invalid_and_duplicate_rows_report_line(tmp_path: Path) -> None:
    row = json.loads((ROOT / "data/voice_bible/ru.jsonl").read_text().splitlines()[0])
    target = tmp_path / "bad.jsonl"
    target.write_text(json.dumps(row) + "\n{broken")
    with pytest.raises(VoiceBibleValidationError, match=r"bad\.jsonl:2"):
        VoiceBible.load(target)
    duplicate = dict(row, id="duplicate-id")
    target.write_text("\n".join((json.dumps(row), json.dumps(duplicate))))
    with pytest.raises(VoiceBibleValidationError, match=r"bad\.jsonl:2.*duplicate"):
        VoiceBible.load(target)
