import json
import sys
from itertools import product
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.persona.ablation import AblationConfig, AblationConfigError


@pytest.mark.parametrize("stages", list(product((False, True), repeat=3)))
def test_each_stage_switches_independently(stages) -> None:
    config = AblationConfig(*stages).validate()
    assert (config.stage1, config.stage2, config.stage3) == stages


def test_prompt_only_baseline_disables_all_numeric_stages() -> None:
    baseline = AblationConfig(
        stage1=False,
        stage2=False,
        stage3=False,
        baseline_prompt_only=True,
    ).validate()
    assert baseline.stage1 is False
    with pytest.raises(AblationConfigError, match="requires"):
        AblationConfig(baseline_prompt_only=True).validate()


def test_snapshot_is_complete_and_json_serializable() -> None:
    config = AblationConfig(stage2=False).validate()
    snapshot = config.snapshot()
    assert snapshot == {
        "stage1": True,
        "stage2": False,
        "stage3": True,
        "baseline_prompt_only": False,
    }
    assert json.loads(json.dumps(snapshot)) == snapshot


def test_non_boolean_switch_is_rejected() -> None:
    with pytest.raises(AblationConfigError, match="booleans"):
        AblationConfig(stage1=1).validate()
