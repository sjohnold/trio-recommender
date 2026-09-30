"""Explicit, intentionally unconfigured llama.cpp backend seam."""

from typing import Any

from trio.inference.protocol import InferenceBackend, InferenceRequest


class BackendNotConfigured(RuntimeError):
    pass


class LlamaCppAdapter:
    def stream(self, request: InferenceRequest):
        raise BackendNotConfigured("llama.cpp backend is not configured")

    async def cancel(self, request_id: str):
        raise BackendNotConfigured("llama.cpp backend is not configured")

    async def loaded_models(self):
        raise BackendNotConfigured("llama.cpp backend is not configured")


def create_backend(settings: Any) -> InferenceBackend:
    backend = getattr(settings, "inference_backend", "ollama")
    if backend == "ollama":
        from trio.inference.ollama import OllamaBackend

        return OllamaBackend(settings=settings)
    if backend in {"llamacpp", "llama.cpp"}:
        raise BackendNotConfigured("llama.cpp backend is not configured")
    raise ValueError(f"unknown inference backend: {backend}")
