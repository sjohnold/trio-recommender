import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.persona.presets import (
    PresetVersionError,
    TrioPreset,
    load_preset,
    save_preset,
)

DEFAULT = Path(__file__).parents[2] / "data/presets/default-trio.json"


def test_round_trip_has_no_data_loss(tmp_path: Path) -> None:
    original = load_preset(DEFAULT)
    target = tmp_path / "nested/preset.json"
    save_preset(original, target)
    assert load_preset(target) == original
    assert json.loads(target.read_text()) == original.model_dump(mode="json")
    assert not list(target.parent.glob(f".{target.name}.*"))


def test_unknown_version_is_not_migrated(tmp_path: Path) -> None:
    data = json.loads(DEFAULT.read_text())
    data["version"] = "99.0.0"
    path = tmp_path / "future.json"
    path.write_text(json.dumps(data))
    with pytest.raises(PresetVersionError) as caught:
        load_preset(path)
    assert (caught.value.found, caught.value.supported) == ("99.0.0", "1.0.0")


@pytest.mark.parametrize("path", ["../escape.json", "preset.txt"])
def test_unsafe_path_is_rejected(path: str) -> None:
    with pytest.raises(ValueError):
        load_preset(path)


def test_duplicate_roles_are_rejected() -> None:
    data = json.loads(DEFAULT.read_text())
    data["personas"][1]["role"] = data["personas"][0]["role"]
    with pytest.raises(ValueError, match="unique roles"):
        TrioPreset.model_validate(data)
