import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trio.inference.protocol import (
    ChunkKind,
    InferenceBackend,
    TokenChunk,
)
def test_chunk_kinds_are_distinct_and_backend_neutral() -> None:
    assert {kind.value for kind in ChunkKind} == {
        "content", "thinking", "done", "error",
    }
    assert "ollama" not in Path(
        ROOT / "src/trio/inference/protocol.py"
    ).read_text().lower()
    assert hasattr(InferenceBackend, "stream")
    assert hasattr(InferenceBackend, "cancel")
    assert hasattr(InferenceBackend, "loaded_models")
@pytest.mark.parametrize(
    ("kind", "text", "error"),
    [
        (ChunkKind.CONTENT, "answer", None),
        (ChunkKind.THINKING, "internal", None),
        (ChunkKind.DONE, "", None),
        (ChunkKind.ERROR, "", "bad_chunk"),
    ],
)
def test_valid_chunk_shapes(kind, text, error) -> None:
    chunk = TokenChunk("request-1", kind, text, error)
    assert chunk.kind is kind
@pytest.mark.parametrize(
    ("kind", "text", "error"),
    [
        (ChunkKind.CONTENT, "", None),
        (ChunkKind.THINKING, "", None),
        (ChunkKind.ERROR, "", None),
        (ChunkKind.DONE, "", "unexpected"),
    ],
)
def test_invalid_chunk_shapes_are_rejected(kind, text, error) -> None:
    with pytest.raises(ValueError):
        TokenChunk("request-1", kind, text, error)
