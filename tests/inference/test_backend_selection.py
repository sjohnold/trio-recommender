import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

from trio.inference.llamacpp import BackendNotConfigured, create_backend


def settings(backend=None):
    values = {"ollama_url": "http://127.0.0.1:11434"}
    if backend is not None:
        values["inference_backend"] = backend
    return SimpleNamespace(**values)


def test_ollama_is_default_backend() -> None:
    assert type(create_backend(settings())).__name__ == "OllamaBackend"
    assert type(create_backend(settings("ollama"))).__name__ == "OllamaBackend"


def test_llamacpp_is_an_explicit_unconfigured_seam() -> None:
    with pytest.raises(BackendNotConfigured, match="not configured"):
        create_backend(settings("llama.cpp"))


def test_unknown_backend_is_rejected_and_domains_stay_neutral() -> None:
    with pytest.raises(ValueError, match="unknown inference backend"):
        create_backend(settings("cloud"))
    for relative in (
        "src/trio/inference/protocol.py",
        "src/trio/inference/router.py",
    ):
        text = (ROOT / relative).read_text().lower()
        assert "ollamabackend" not in text
        assert "llamacppadapter" not in text
