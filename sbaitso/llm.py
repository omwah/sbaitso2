"""LLM transports: Ollama (default, local) and any OpenAI-compatible API.

Zero SDKs — just httpx against the streaming HTTP endpoints.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

DEFAULT_OLLAMA_URL = os.environ.get("SBAITSO_OLLAMA_URL", "http://127.0.0.1:11434")


@dataclass(frozen=True)
class RemoteProvider:
    key_env: str
    base_url: str
    model: str


# OpenAI-compatible providers only. Explicit CLI/SBAITSO_REMOTE_* settings win.
REMOTE_PROVIDERS = (
    RemoteProvider("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
    RemoteProvider("GROQ_API_KEY", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    RemoteProvider("TOGETHER_API_KEY", "https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    RemoteProvider("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    RemoteProvider("MISTRAL_API_KEY", "https://api.mistral.ai/v1", "mistral-small-latest"),
    RemoteProvider("CEREBRAS_API_KEY", "https://api.cerebras.ai/v1", "llama3.1-8b"),
)


def detected_remote_provider() -> RemoteProvider | None:
    """Return the first configured supported OpenAI-compatible provider."""
    return next((provider for provider in REMOTE_PROVIDERS if os.environ.get(provider.key_env)), None)


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or DEFAULT_OLLAMA_URL).rstrip("/")
        self.model = model or os.environ.get("SBAITSO_MODEL")
        self.timeout = timeout
        self._resolved: str | None = None

    async def healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def resolve_model(self) -> str:
        if self.model:
            return self.model
        if self._resolved:
            return self._resolved
        names: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(f"{self.base_url}/api/tags")
                r.raise_for_status()
                names = [m["name"] for m in r.json().get("models", [])]
        except Exception:
            names = []
        for pref in ("llama3.1", "llama3", "qwen2.5", "qwen2", "mistral", "gemma2", "phi3"):
            for n in names:
                if n.startswith(pref):
                    self._resolved = n
                    return n
        self._resolved = names[0] if names else "llama3.1"
        return self._resolved

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {
            "model": await self.resolve_model(),
            "messages": messages,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            async with c.stream("POST", f"{self.base_url}/api/chat", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = (data.get("message") or {}).get("content", "")
                    if delta:
                        yield delta


class RemoteClient:
    """OpenAI-compatible remote API (optional rung 2 of the ladder)."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        provider = detected_remote_provider()
        self.provider = "custom" if api_key or os.environ.get("SBAITSO_REMOTE_KEY") else (
            provider.key_env if provider else None
        )
        self.api_key = api_key or os.environ.get("SBAITSO_REMOTE_KEY", "") or (
            os.environ.get(provider.key_env, "") if provider else ""
        )
        self.base_url = (
            base_url or os.environ.get("SBAITSO_REMOTE_URL") or
            (provider.base_url if provider else "https://api.openai.com/v1")
        ).rstrip("/")
        self.model = model or os.environ.get("SBAITSO_REMOTE_MODEL") or (
            provider.model if provider else "gpt-4o-mini"
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def healthy(self) -> bool:
        if not self.configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=self._headers()) as c:
                r = await c.get(f"{self.base_url}/models")
                return r.status_code == 200
        except Exception:
            return False

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {"model": self.model, "messages": messages, "stream": True}
        async with httpx.AsyncClient(timeout=120.0, headers=self._headers()) as c:
            async with c.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = obj.get("choices") or [{}]
                    delta = (choices[0].get("delta") or {}).get("content", "")
                    if delta:
                        yield delta
