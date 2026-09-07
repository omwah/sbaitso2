"""Native voice: espeak-ng through asyncio.subprocess.

Honors the authentic 0-9 dot-command scales. If espeak-ng is not on the
machine, voice silently disables — the doctor still talks in text,
exactly like a Sound Blaster-less 1991 PC.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass


def available() -> bool:
    return shutil.which("espeak-ng") is not None


@dataclass
class VoiceState:
    """Mirrors the engine's voice settings on the frontend side."""

    tone: int = 1
    volume: int = 5
    pitch: int = 5
    speed: int = 3
    on: bool = True

    def update(self, ev) -> None:
        """Apply a VoiceParams or VoiceEnabled event."""
        tone = getattr(ev, "tone", None)
        volume = getattr(ev, "volume", None)
        pitch = getattr(ev, "pitch", None)
        speed = getattr(ev, "speed", None)
        if tone is not None:
            self.tone = tone
        if volume is not None:
            self.volume = volume
        if pitch is not None:
            self.pitch = pitch
        if speed is not None:
            self.speed = speed
        if hasattr(ev, "on"):
            self.on = ev.on


def espeak_args(state: VoiceState, echo: bool = False) -> list[str]:
    """Map the 0-9 scales to espeak-ng flags.

    - volume 0-9  -> -a amplitude 0-200
    - pitch  0-9  -> -p pitch 0-99 (5..95)
    - speed  0-9  -> -s words/min 100..370
    - tone   0/1  -> voice variant + pitch offset (bass/treble)
    """
    voice = "en-us+f3" if echo else "en-us+f2"
    pitch = 5 + state.pitch * 10
    if echo:
        pitch += 15
    elif state.tone == 0:  # bass
        pitch = max(0, pitch - 20)
    elif state.tone == 1:  # treble
        pitch = min(99, pitch + 5)
    speed = 100 + state.speed * 30
    amplitude = int(state.volume * (200 / 9))
    return [
        "-v", voice,
        "-p", str(pitch),
        "-s", str(speed),
        "-a", str(amplitude),
    ]


class EspeakVoice:
    """Fire-and-forget espeak-ng; speech overlaps the typewriter, as 1991 intended."""

    def __init__(self) -> None:
        self._pending: set[asyncio.Task] = set()

    async def speak(
        self, text: str, state: VoiceState, echo: bool = False
    ) -> asyncio.Task | None:
        """Start one utterance and return its reaping task.

        The caller types the matching line while this runs, then awaits the
        returned task before advancing to the next line. That keeps speech
        sequential without making the typewriter wait for it to begin.
        """
        if not state.on or not text.strip() or not available():
            return None
        clean = text.replace("\n", " ")
        try:
            proc = await asyncio.create_subprocess_exec(
                "espeak-ng", *espeak_args(state, echo), clean,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError:
            return None
        task = asyncio.create_task(proc.wait())
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)
        return task

    async def drain(self) -> None:
        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)
