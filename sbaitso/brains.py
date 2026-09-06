"""The brain ladder: Ollama -> Remote API -> Retro v1 (1991 mode).

The doctor never refuses to see you.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from .llm import OllamaClient, RemoteClient
from .retro import RetroEngine


@dataclass
class BrainContext:
    """Extra context non-LLM brains need (LLM brains ignore it)."""

    user_text: str
    name: str | None = None


class Brain:
    name: str = "BRAIN"

    async def healthy(self) -> bool:  # pragma: no cover - overridden
        return False

    async def stream(
        self, messages: list[dict], ctx: BrainContext
    ) -> AsyncIterator[str]:  # pragma: no cover - overridden
        yield ""


class OllamaBrain(Brain):
    def __init__(self, client: OllamaClient) -> None:
        self.client = client
        self.name = "OLLAMA"
        self.down = False

    async def healthy(self) -> bool:
        return await self.client.healthy()

    async def stream(self, messages, ctx) -> AsyncIterator[str]:
        async for delta in self.client.stream_chat(messages):
            yield delta


class RemoteBrain(Brain):
    def __init__(self, client: RemoteClient) -> None:
        self.client = client
        self.name = "REMOTE MAINFRAME"
        self.down = False

    async def healthy(self) -> bool:
        return await self.client.healthy()

    async def stream(self, messages, ctx) -> AsyncIterator[str]:
        async for delta in self.client.stream_chat(messages):
            yield delta


class RetroBrain(Brain):
    """Always healthy. Never fails. Never smart."""

    def __init__(self, retro: RetroEngine) -> None:
        self.retro = retro
        self.name = "RETRO v1 (1991)"
        self.down = False

    async def healthy(self) -> bool:
        return True

    async def stream(self, messages, ctx) -> AsyncIterator[str]:
        yield self.retro.respond(ctx.user_text, ctx.name)
