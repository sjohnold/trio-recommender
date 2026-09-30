import csv
import sys
from io import StringIO
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
from trio.experiments.report import build_report


def run_set():
    return {
        "annotation_version": "review-v2",
        "digests": {"actor": "sha256:11111111", "state": "sha256:22222222"},
        "results": {
            "H1": {
                "metric": "drift_onset_turn", "values": [4, 6, None, 8],
                "comparison": [8, 10, 12], "failures": 1,
            },
            "H2": {"metric": "distance_auc", "values": [None], "failures": 2},
        },
    }


def rows(artifacts):
    return list(csv.DictReader(StringIO(artifacts.csv)))


def test_report_has_measured_or_insufficient_row_for_every_hypothesis():
    artifacts = build_report(run_set())
    data = rows(artifacts)
    assert [row["hypothesis"] for row in data] == ["H1", "H2", "H3", "H4", "H5"]
    assert data[0]["status"] == "measured"
    assert all(row["status"] == "insufficient-data" for row in data[1:])
    assert (data[0]["n"], data[0]["missing"], data[0]["mean"],
            data[0]["median"], data[0]["failures"]) == ("3", "1", "6", "6", "1")


def test_uncertainty_effect_digests_and_annotation_are_exported():
    artifacts = build_report(run_set())
    first = rows(artifacts)[0]
    assert first["ci_low"] and first["ci_high"] and first["effect_size"]
    assert "actor=sha256:11111111" in first["digests"]
    assert first["annotation_version"] == "review-v2"
    assert "Manual annotation: `review-v2`" in artifacts.markdown
    assert "proved" not in artifacts.markdown.lower()
    assert build_report(run_set()) == artifacts


def test_unversioned_manual_annotation_is_rejected():
    value = run_set()
    value["annotation_version"] = ""
    with pytest.raises(ValueError, match="annotation_version"):
        build_report(value)
    value = run_set()
    value["digests"] = {}
    with pytest.raises(ValueError, match="digests"):
        build_report(value)
