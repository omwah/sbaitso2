"""Engine events — the adapter contract between the core and frontends.

The core yields Events; each frontend (native terminal, web xterm.js)
renders them. Nothing else is frontend-specific.

Note: delay_ms is declared last in each event so the event's own
fields come first positionally (e.g. Line("text", color="cyan")).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


class Event:
    """Base class. Not a dataclass so subclasses control field order."""

    delay_ms: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)  # type: ignore[arg-type]
        d["type"] = type(self).__name__.lower()
        return d


@dataclass
class Line(Event):
    """Raw terminal output (banners, listings). No voice, no typewriter."""

    text: str = ""
    color: str = "white"  # white|cyan|yellow|green|red|dim
    reveal: bool = False
    delay_ms: int = 0


@dataclass
class Say(Event):
    """Doctor speech: typewriter reveal + TTS.

    ``partial`` appends streamed LLM text without audio. ``line_end`` lets a
    stream keep all of its chunks on one display line. A final event can carry
    ``speech_text`` so the frontend speaks the complete sentence once, rather
    than stuttering one token at a time.

    voice: "main" for the doctor, "echo" for the .ECHO second voice.
    """

    text: str = ""
    reveal: bool = True
    voice: str = "main"
    partial: bool = False
    line_end: bool = True
    speech_text: str | None = None
    delay_ms: int = 0


@dataclass
class Beep(Event):
    """PC-speaker style beep (Web Audio square wave / terminal BEL)."""

    freq: float = 880.0
    ms: int = 120
    delay_ms: int = 0


@dataclass
class Bell(Event):
    """Attention bell."""

    delay_ms: int = 0


@dataclass
class Palette(Event):
    """Switch color theme: cga1|cga2|ega|vga|amber."""

    name: str = "cga1"
    announce: bool = True
    delay_ms: int = 0


@dataclass
class Clear(Event):
    """Clear the screen (used by the PARITY ERROR reset)."""

    delay_ms: int = 0


@dataclass
class Prompt(Event):
    """Engine wants a line of input; label decorates the prompt."""

    label: str = ""
    delay_ms: int = 0


@dataclass
class VoiceParams(Event):
    """TTS parameters changed via .TONE/.VOLUME/.PITCH/.SPEED/.PARAM."""

    tone: int | None = None
    volume: int | None = None
    pitch: int | None = None
    speed: int | None = None
    delay_ms: int = 0


@dataclass
class VoiceEnabled(Event):
    """Voice toggled via VOICE ON/OFF."""

    on: bool = True
    delay_ms: int = 0


@dataclass
class EchoMode(Event):
    """.ECHO ON/OFF toggled."""

    on: bool = False
    delay_ms: int = 0


@dataclass
class Quit(Event):
    """Session over; error=True denotes an unrecoverable startup failure."""

    error: bool = False
    delay_ms: int = 0
