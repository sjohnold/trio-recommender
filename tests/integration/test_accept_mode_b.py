import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
from accept_mode_b import FEATURES, ROLES, accept_mode_b


def evidence():
    return {
        "residents": [
            {"name": "actor", "digest": "sha256:actor", "state": False},
            {"name": "state", "digest": "sha256:state", "state": True},
        ],
        "routes": {
            role: {"actor_digest": "sha256:actor", "memory_key": role}
            for role in ROLES
        },
        "role_memories": {
            role: {"id": f"memory-{role}", "turns": []} for role in ROLES
        },
        "features": dict.fromkeys(FEATURES, True),
        "languages": ["ru", "en", "sr"],
        "voice_vectors": {
            "pragmatist": {"directness": 1.0, "warmth": 0.0},
            "logician": {"directness": 0.4, "warmth": -0.4},
            "empath": {"directness": 0.0, "warmth": 1.0},
        },
    }


def test_accepts_single_actor_state_and_full_feature_parity():
    result = accept_mode_b(evidence())
    assert result.passed and result.reasons == ()
    assert set(result.voice_distances) == {
        "pragmatist:logician", "pragmatist:empath", "logician:empath",
    }


def test_rejects_shared_memory_and_missing_mode_a_feature():
    value = evidence()
    value["role_memories"]["empath"]["id"] = "memory-logician"
    value["features"]["experiments"] = False
    assert set(accept_mode_b(value).reasons) == {
        "role_memory_not_isolated", "feature_parity_failed",
    }


def test_voice_averaging_is_measured_and_fails_explicitly():
    value = evidence()
    shared = {"directness": 0.5, "warmth": 0.5}
    value["voice_vectors"] = {role: shared for role in ROLES}
    result = accept_mode_b(value)
    assert result.reasons == ("voice_averaging_detected",)
    assert set(result.voice_distances.values()) == {0.0}
    json.dumps(result.voice_distances)
