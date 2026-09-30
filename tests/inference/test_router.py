import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trio.contracts import Language, Mode, Role
from trio.inference.residency import ResidencyReport
from trio.inference.router import ModelRef, ModelRouter

READY = ResidencyReport(True, "admitted", ("p", "l", "e", "s"), 4, 8)
A = {
    Role.PRAGMATIST: ModelRef("p", "digest-p", "qwen"),
    Role.LOGICIAN: ModelRef("l", "digest-l", "gemma"),
    Role.EMPATH: ModelRef("e", "digest-e", "llama"),
}
SHARED = ModelRef("shared", "digest-shared", "mistral")
STATE = ModelRef("state", "digest-state", "smollm")


def router(report=READY):
    return ModelRouter(A, SHARED, STATE, report)


def test_mode_a_routes_each_role_and_mode_b_shares_actor() -> None:
    routed_a = [router().resolve(Mode.A, role) for role in Role]
    routed_b = [router().resolve(Mode.B, role) for role in Role]
    assert len({item.name for item in routed_a}) == 3
    assert {item.name for item in routed_b} == {"shared"}
    assert {item.memory_key for item in routed_b} == {role.value for role in Role}
    for item in (*routed_a, *routed_b):
        assert item.capabilities == {"streaming", "cancel", "metrics"}
        assert item.languages == set(Language)
    assert router().resolve_state() is STATE


def test_session_snapshot_uses_digests_and_keeps_three_role_keys() -> None:
    snapshot = router().snapshot("B")
    assert snapshot["actor_digests"] == {
        role.value: "digest-shared" for role in Role
    }
    assert snapshot["state_digest"] == "digest-state"
    assert all("digest" in value for value in snapshot["actor_digests"].values())


def test_mode_a_refuses_failed_residency() -> None:
    failed = ResidencyReport(False, "over_budget", (), 9, 8)
    with pytest.raises(RuntimeError, match="over_budget"):
        router(failed).resolve("A", "pragmatist")
