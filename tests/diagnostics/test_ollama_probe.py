import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from trio.diagnostics import ollama_probe
from trio.diagnostics.ollama_probe import OllamaProbeStatus, probe_ollama


def install_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        ollama_probe.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )


def test_healthy_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payloads = {
            "/api/version": {"version": "0.9.0"},
            "/api/tags": {"models": [{"name": "actor:latest"}]},
        }
        return httpx.Response(200, json=payloads.get(request.url.path, {}))

    install_transport(monkeypatch, handler)
    result = asyncio.run(probe_ollama("http://127.0.0.1:11434", 1))
    assert result.status is OllamaProbeStatus.HEALTHY
    assert (result.version, result.tags) == ("0.9.0", ("actor:latest",))


@pytest.mark.parametrize(
    ("error_type", "status"),
    [
        (httpx.ConnectError, OllamaProbeStatus.UNAVAILABLE),
        (httpx.ReadTimeout, OllamaProbeStatus.TIMEOUT),
    ],
)
def test_transport_errors(monkeypatch, error_type, status) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error_type("failure", request=request)

    install_transport(monkeypatch, handler)
    result = asyncio.run(probe_ollama("http://localhost:11434", 1))
    assert result.status is status


def test_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": 3})

    install_transport(monkeypatch, handler)
    result = asyncio.run(probe_ollama("http://[::1]:11434", 1))
    assert result.status is OllamaProbeStatus.MALFORMED


def test_external_url_is_rejected() -> None:
    with pytest.raises(ValueError, match="loopback"):
        asyncio.run(probe_ollama("https://example.com", 1))
