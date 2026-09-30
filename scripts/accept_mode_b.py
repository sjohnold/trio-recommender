#!/usr/bin/env python3
"""Mode B feature-parity and role-separation acceptance."""
import argparse
import json
from dataclasses import asdict, dataclass
from itertools import combinations
from math import sqrt
from statistics import fmean

ROLES = ("pragmatist", "logician", "empath")
FEATURES = ("streaming", "cancel", "live_stats", "languages", "metrics", "experiments")


@dataclass(frozen=True, slots=True)
class Acceptance:
    passed: bool
    reasons: tuple[str, ...]
    voice_distances: dict[str, float]


def _distances(vectors):
    result = {}
    for left, right in combinations(ROLES, 2):
        a, b = vectors.get(left), vectors.get(right)
        if not a or set(a) != set(b):
            continue
        result[f"{left}:{right}"] = sqrt(fmean(
            (float(a[key]) - float(b[key])) ** 2 for key in a
        ))
    return result


def accept_mode_b(evidence) -> Acceptance:
    reasons = []
    residents = evidence.get("residents", [])
    actors = [item for item in residents if not item.get("state")]
    states = [item for item in residents if item.get("state")]
    if len(actors) != 1 or len(states) != 1:
        reasons.append("resident_set_mismatch")
        actor_digest = None
    else:
        actor_digest = actors[0].get("digest")
        if not actor_digest or not states[0].get("digest"):
            reasons.append("missing_model_digest")
        elif actor_digest == states[0]["digest"]:
            reasons.append("state_not_separate")
    routes = evidence.get("routes", {})
    if set(routes) != set(ROLES) or any(
        route.get("actor_digest") != actor_digest or route.get("memory_key") != role
        for role, route in routes.items()
    ):
        reasons.append("role_route_mismatch")
    memories = evidence.get("role_memories", {})
    memory_ids = [memories.get(role, {}).get("id") for role in ROLES]
    if set(memories) != set(ROLES) or None in memory_ids or len(set(memory_ids)) != 3:
        reasons.append("role_memory_not_isolated")
    parity = evidence.get("features", {})
    if set(parity) != set(FEATURES) or not all(parity.values()):
        reasons.append("feature_parity_failed")
    if set(evidence.get("languages", ())) != {"ru", "en", "sr"}:
        reasons.append("language_parity_failed")
    distances = _distances(evidence.get("voice_vectors", {}))
    if len(distances) != 3:
        reasons.append("voice_averaging_unmeasured")
    elif min(distances.values()) == 0:
        reasons.append("voice_averaging_detected")
    return Acceptance(not reasons, tuple(reasons), distances)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=argparse.FileType())
    args = parser.parse_args()
    result = accept_mode_b(json.load(args.evidence))
    print(json.dumps(asdict(result), ensure_ascii=False))
    raise SystemExit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
