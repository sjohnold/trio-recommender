"""Validated settings for the loopback-only Trio runtime."""

from pathlib import Path
from typing import Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRIO_", extra="forbid")

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    ollama_url: str = "http://127.0.0.1:11434"
    database_path: Path = Path("data/trio.db")
    cloud_endpoint: str | None = None

    @field_validator("host")
    @classmethod
    def require_loopback_host(cls, value: str) -> str:
        if value.lower() not in _LOOPBACK_HOSTS:
            raise ValueError("host must be a loopback address")
        return value

    @field_validator("ollama_url")
    @classmethod
    def require_loopback_ollama(cls, value: str) -> str:
        parsed = urlsplit(value)
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("ollama_url contains an invalid port") from exc
        if (
            parsed.scheme != "http"
            or parsed.hostname not in _LOOPBACK_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("ollama_url must be an unauthenticated loopback HTTP URL")
        return value.rstrip("/")

    @field_validator("cloud_endpoint")
    @classmethod
    def reject_cloud_endpoint(cls, value: str | None) -> None:
        if value is not None:
            raise ValueError("cloud endpoints are not supported")
        return None

    @classmethod
    def load(cls) -> Self:
        return cls()
