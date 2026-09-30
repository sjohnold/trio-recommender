import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.contracts import Language, Role
from trio.language.contracts import LanguageLock
from trio.persona.ablation import AblationConfig
from trio.persona.models import AlignmentPolicyKey, PersonaStats
from trio.persona.selector import select_examples
from trio.persona.voice_query import VoiceQuery

STATS = PersonaStats(
    energy=6, openness=7, nerve=4, sharpness=5,
    reasoning=8, provocation=3, attunement=6,
)
LOCK = LanguageLock(language=Language.EN)
QUERY = VoiceQuery(
    language=LOCK, role=Role.LOGICIAN, stats=STATS,
    alignment=AlignmentPolicyKey.LAWFUL_NEUTRAL,
)


@dataclass(frozen=True)
class Example:
    id: str
    text: str
    topic: str
    language: LanguageLock = LOCK
    role: Role = Role.LOGICIAN
    stats: PersonaStats = STATS
    alignment: AlignmentPolicyKey = AlignmentPolicyKey.LAWFUL_NEUTRAL


@dataclass(frozen=True)
class PromptParts:
    stage1_enabled: bool
    stage2_enabled: bool
    voice_examples: tuple[str, ...]


EXAMPLES = [
    Example("a", "First voice sample.", "facts"),
    Example("b", "Second voice sample.", "logic"),
    Example("c", "Third voice sample.", "dialogue"),
]


def assemble_prompt_parts(config: AblationConfig) -> PromptParts:
    config.validate()
    selected = select_examples(QUERY, EXAMPLES) if config.stage3 else []
    return PromptParts(
        stage1_enabled=config.stage1,
        stage2_enabled=config.stage2,
        voice_examples=tuple(example.text for example in selected),
    )


def test_stage3_disabled_yields_no_voice_examples() -> None:
    parts = assemble_prompt_parts(AblationConfig(stage3=False))
    assert parts.voice_examples == ()


def test_prompt_only_baseline_has_no_persona_or_worldview_hints() -> None:
    baseline = AblationConfig(False, False, False, True)
    serialized = json.dumps(asdict(assemble_prompt_parts(baseline)))
    assert serialized == (
        '{"stage1_enabled": false, "stage2_enabled": false, '
        '"voice_examples": []}'
    )
    assert QUERY.alignment.value not in serialized
    assert all(name not in serialized for name in type(STATS).model_fields)


def test_h2_variants_receive_only_enabled_stages() -> None:
    for stage1 in (False, True):
        for stage2 in (False, True):
            for stage3 in (False, True):
                config = AblationConfig(stage1, stage2, stage3)
                parts = assemble_prompt_parts(config)
                assert parts.stage1_enabled is stage1
                assert parts.stage2_enabled is stage2
                assert bool(parts.voice_examples) is stage3
