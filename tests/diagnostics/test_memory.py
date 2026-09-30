import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.diagnostics import memory
from trio.diagnostics.memory import GIB, AdmissionReason, MemorySnapshot, ProfileName
from trio.diagnostics.memory import ResidentModel, admit, select_profile

def test_base_is_selected_for_eight_gib() -> None:
    profile = select_profile(MemorySnapshot(8 * GIB), None)
    assert (profile.name, profile.num_ctx) == (ProfileName.BASE, 4096)

def test_requested_profile_cannot_exceed_memory() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        select_profile(MemorySnapshot(8 * GIB), ProfileName.PLUS)

def test_admission_counts_state_vram_and_reserve() -> None:
    profile = select_profile(MemorySnapshot(8 * GIB), ProfileName.BASE)
    models = [
        ResidentModel("actor", 7 * GIB, 6 * GIB),
        ResidentModel("state", GIB // 2, GIB // 2, is_state=True),
    ]
    result = admit(models, profile)
    assert result.admitted
    assert result.required_bytes == 6 * GIB + GIB // 2

def test_unknown_size_is_rejected() -> None:
    profile = select_profile(MemorySnapshot(8 * GIB), None)
    result = admit([ResidentModel("state", None, is_state=True)], profile)
    assert result.reason is AdmissionReason.UNKNOWN_SIZE

def test_over_budget_and_missing_state_are_rejected() -> None:
    profile = select_profile(MemorySnapshot(8 * GIB), None)
    over = admit([ResidentModel("state", 8 * GIB, is_state=True)], profile)
    missing = admit([ResidentModel("actor", GIB)], profile)
    assert over.reason is AdmissionReason.OVER_BUDGET
    assert missing.reason is AdmissionReason.MISSING_STATE_MODEL

def test_detect_memory_falls_back_to_ram(monkeypatch) -> None:
    monkeypatch.setattr(memory.os, "sysconf", lambda key: 1024)
    monkeypatch.setattr(memory.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    assert memory.detect_memory() == MemorySnapshot(1024**2)
