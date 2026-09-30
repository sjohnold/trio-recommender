import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
TEXT = (ROOT / "ACCEPTANCE.md").read_text()


def rows():
    result = []
    for line in TEXT.splitlines():
        if not line.startswith("| ") or line.startswith("| ID ") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 8
        result.append(cells)
    return result


def test_manifest_has_unique_typed_evidence_for_all_acceptance_areas():
    data = rows()
    assert len({row[0] for row in data}) == len(data)
    assert {row[2] for row in data} <= {"PASS", "FAIL", "BLOCKED"}
    assert all(re.fullmatch(r"2026-\d\d-\d\d", row[3]) for row in data)
    assert all(row[4] and row[5].startswith("`") and row[5].endswith("`")
               for row in data)
    assert all(row[6].startswith("`") and row[6].endswith("`") for row in data)
    areas = {row[1] for row in data}
    assert {"H1", "H2", "H3", "H4", "H5", "UI session flow",
            "Mode A gate", "Mode B parity", "Language boundaries",
            "Runtime boundaries"} <= areas


def test_every_pass_points_to_existing_evidence_and_no_claim_says_works():
    for row in rows():
        evidence = row[6].strip("`")
        if row[2] == "PASS":
            assert (ROOT / evidence).exists(), row[0]
    assert "работает" not in TEXT.lower()
    assert "гипотеза доказана" in TEXT.lower()
    assert "не считается подтверждённой автоматически" in TEXT


def test_open_hardware_science_and_review_gaps_are_blocked():
    statuses = {row[0]: row[2] for row in rows()}
    assert statuses["UI-REAL"] == "BLOCKED"
    assert statuses["MODE-A-REAL"] == "BLOCKED"
    assert statuses["SR-REVIEW"] == "BLOCKED"
    assert statuses["MODEL-GATE"] == "BLOCKED"
    assert statuses["POWER"] == "BLOCKED"
    assert all(row[4] == "PENDING" for row in rows() if row[2] == "BLOCKED")


def test_boundaries_forbid_external_runtime_and_unversioned_results():
    lower = TEXT.lower()
    for phrase in (
        "loopback", "cloud fallback", "model unload", "отключение unconditional",
        "отсутствующий digest", "pooled primary", "незаверсионированная",
    ):
        assert phrase in lower
