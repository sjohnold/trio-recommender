"""Typed availability probe for a loopback Ollama server."""

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

import httpx

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class OllamaProbeStatus(StrEnum):
    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    MALFORMED = "malformed_response"


@dataclass(frozen=True, slots=True)
class OllamaProbeResult:
    status: OllamaProbeStatus
    version: str | None = None
    tags: tuple[str, ...] = ()
    detail: str | None = None


def _validate_target(base_url: str, timeout_s: float) -> str:
    parsed = urlsplit(base_url)
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("base_url contains an invalid port") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in _LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("base_url must be an unauthenticated loopback HTTP URL")
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    return base_url.rstrip("/")


async def probe_ollama(base_url: str, timeout_s: float) -> OllamaProbeResult:
    target = _validate_target(base_url, timeout_s)
    try:
        async with httpx.AsyncClient(base_url=target, timeout=timeout_s) as client:
            health = await client.get("/")
            health.raise_for_status()
            version_response = await client.get("/api/version")
            version_response.raise_for_status()
            tags_response = await client.get("/api/tags")
            tags_response.raise_for_status()
        version_data = version_response.json()
        tags_data = tags_response.json()
        version = version_data["version"]
        models = tags_data["models"]
        if not isinstance(version, str) or not version or not isinstance(models, list):
            raise TypeError("invalid version or models")
        tags = tuple(model["name"] for model in models)
        if not all(isinstance(tag, str) and tag for tag in tags):
            raise TypeError("invalid model name")
        return OllamaProbeResult(OllamaProbeStatus.HEALTHY, version, tags)
    except httpx.TimeoutException as exc:
        return OllamaProbeResult(OllamaProbeStatus.TIMEOUT, detail=str(exc))
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        return OllamaProbeResult(OllamaProbeStatus.UNAVAILABLE, detail=str(exc))
    except (KeyError, TypeError, ValueError) as exc:
        return OllamaProbeResult(OllamaProbeStatus.MALFORMED, detail=str(exc))

