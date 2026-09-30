import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trio.contracts import Role
from trio.orchestrator.alignment import policy_for
from trio.orchestrator.turns import TurnContext, score_candidate


def persona(role, energy=5, provocation=5):
    return SimpleNamespace(
        role=role,
        stats=SimpleNamespace(energy=energy, provocation=provocation),
    )


def ranking(last_role=None):
    scores = [
        score_candidate(
            TurnContext(last_role, relevance=0.5),
            persona(role),
            policy_for("true_neutral"),
        )
        for role in Role
    ]
    return [item.role for item in sorted(
        scores, key=lambda item: (-item.total, item.role.value)
    )]


def test_base_order_is_pragmatist_logician_empath() -> None:
    assert ranking() == [Role.PRAGMATIST, Role.LOGICIAN, Role.EMPATH]
    assert ranking(Role.PRAGMATIST)[0] is Role.LOGICIAN
    assert ranking(Role.LOGICIAN)[0] is Role.EMPATH


def test_components_are_preserved_and_deterministic() -> None:
    context = TurnContext(
        Role.EMPATH, 0.8, addressed=True, cooldown_active=True,
        repetition=0.2, timeout_risk=0.3,
    )
    candidate = persona(Role.PRAGMATIST, 8, 7)
    policy = policy_for("lawful_good")
    first = score_candidate(context, candidate, policy)
    second = score_candidate(context, candidate, policy)
    assert first == second
    assert first.total == round(sum((
        first.base, first.relevance, first.address, first.stats,
        first.alignment, first.cooldown, first.risk,
    )), 6)


def test_observer_can_remain_silent() -> None:
    score = score_candidate(
        TurnContext(
            Role.PRAGMATIST, 0, cooldown_active=True,
            repetition=1, timeout_risk=1, observer=True,
        ),
        persona(Role.EMPATH, 1, 1),
        policy_for("chaotic_neutral"),
    )
    assert score.should_speak is False
