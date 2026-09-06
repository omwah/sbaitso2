"""The shared core Engine. Pure-async, zero frontend knowledge.

Frontends iterate `engine.run(inputs)` and render the yielded Events.
Inputs is an async iterator of user lines (None closes the session).
"""

from __future__ import annotations

import asyncio
import random
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from .boot import GLITCH_LINE, banner_events, greeting_events, parity_events, retro_warning
from .brains import Brain, BrainContext, OllamaBrain, RemoteBrain, RetroBrain
from .commands import CommandVM
from .events import Clear, Line, Prompt, Quit, Say
from .llm import OllamaClient, RemoteClient
from .memory import Fact, SessionMemory
from .persona import assemble_messages
from .retro import RetroEngine
from .safety import crisis_response, is_crisis, is_swear, sass_response


class Inputs:
    """Async queue of user input lines; None closes the session."""

    def __init__(self) -> None:
        self._q: asyncio.Queue[str | None] = asyncio.Queue()

    def push(self, item: str | None) -> None:
        self._q.put_nowait(item)

    def close(self) -> None:
        self.push(None)

    def __aiter__(self) -> "Inputs":
        return self

    async def __anext__(self) -> str:
        item = await self._q.get()
        if item is None:
            raise StopAsyncIteration
        return item


@dataclass
class Settings:
    sass: str = "NORMAL"
    palette: str = "cga1"
    echo_on: bool = False
    tone: int = 1
    volume: int = 5
    pitch: int = 5
    speed: int = 5
    fast: bool = False  # native frontend: skip typewriter pacing


@dataclass
class EngineArgs:
    """Everything the engine needs; built from CLI flags or env."""

    brain: str = "auto"  # auto|ollama|remote|retro
    ollama_url: str | None = None
    model: str | None = None
    remote_url: str | None = None
    remote_model: str | None = None
    remote_key: str | None = None
    sass: str = "NORMAL"
    palette: str = "cga1"
    allow_shell: bool = False
    fast: bool = False


_SENTENCE_END = re.compile(r"[.!?]+\s|\n")


class Engine:
    def __init__(self, brains: list[Brain], args: EngineArgs) -> None:
        self.brains = brains
        self.brain = brains[-1]  # sane default; boot() picks properly
        self.args = args
        self.settings = Settings(
            sass=args.sass.upper(), palette=args.palette, fast=args.fast
        )
        self.allow_shell = args.allow_shell
        self.memory = SessionMemory()
        self.retro = RetroEngine()
        self.commands = CommandVM(self)
        self.history: list[dict] = []
        self.topic: str | None = None
        self.quitting = False
        self.swears = 0
        self.rng = random.Random()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_args(cls, args: EngineArgs) -> "Engine":
        brains: list[Brain] = []
        if args.brain != "retro":
            brains.append(OllamaBrain(OllamaClient(args.ollama_url, args.model)))
            remote = RemoteClient(args.remote_key, args.remote_url, args.remote_model)
            if remote.configured or args.brain == "remote":
                brains.append(RemoteBrain(remote))
        brains.append(RetroBrain(cls._shared_retro()))
        if args.brain == "ollama":
            brains = [brains[0], brains[-1]]
        elif args.brain == "remote":
            brains = [b for b in brains if isinstance(b, RemoteBrain)] or [brains[-1]]
            brains = brains + [RetroBrain(cls._shared_retro())]
        return cls(brains, args)

    _retro_instance: RetroEngine | None = None

    @classmethod
    def _shared_retro(cls) -> RetroEngine:
        if cls._retro_instance is None:
            cls._retro_instance = RetroEngine()
        return cls._retro_instance

    def _name(self) -> str:
        return self.memory.name or "FRIEND"

    # ------------------------------------------------------------------
    # Brain ladder management
    # ------------------------------------------------------------------
    async def probe_boot(self) -> AsyncIterator:
        """Probe the ladder at boot; yields result lines."""
        for brain in self.brains:
            if isinstance(brain, RetroBrain):
                continue
            healthy = await brain.healthy()
            brain.down = not healthy
            status = "OK" if healthy else "NOT FOUND"
            yield Line(
                f" Probing {brain.name:<18} {status}",
                color="green" if healthy else "red",
                delay_ms=120,
            )

    def select_best_brain(self) -> Brain:
        for brain in self.brains:
            if not brain.down:
                return brain
        return self.brains[-1]

    def reset_brain_flags(self) -> None:
        for brain in self.brains:
            brain.down = False

    def defrag_history(self) -> int:
        if len(self.history) <= 12:
            return 0
        keep = self.history[-8:]
        removed = len(self.history) - len(keep)
        self.history = keep
        return removed

    # ------------------------------------------------------------------
    # Main session
    # ------------------------------------------------------------------
    async def run(self, inputs: Inputs) -> AsyncIterator:
        async for ev in self._boot():
            yield ev

        # -- intake: name, then age (asked every run; nothing persists) --
        name: str | None = None
        while True:
            yield Prompt("NAME")
            try:
                name = (await anext(inputs)).strip()
            except StopAsyncIteration:
                name = None
                break
            if name:
                break
            yield Say("I DID NOT HEAR A NAME. TRY AGAIN.")

        if name:
            up_name = name.upper()
            if up_name in ("DOCTOR", "DR", "DR.", "SBAITSO", "DR SBAITSO"):
                yield Say("WE WOULD BE COLLEAGUES THEN. I LIKE YOU ALREADY.")
            elif up_name == "SBIASTO":
                yield Say("THAT IS NOT HOW YOU SPELL MY NAME. BUT I ANSWER TO IT ANYWAY.")
            self.memory.name = up_name
            yield Say(f"HELLO, {up_name}.")

            # -- age --
            got_age = False
            for _ in range(3):
                yield Prompt("AGE")
                try:
                    age_line = (await anext(inputs)).strip()
                except StopAsyncIteration:
                    break
                digits = re.search(r"\d{1,3}", age_line)
                if digits:
                    self.memory.age = int(digits.group())
                    self.memory.facts.append(
                        Fact("AGE", f"{self.memory.age} YEARS OLD", 0)
                    )
                    yield Say(age_reaction(self.memory.age))
                    got_age = True
                    break
                yield Say("THAT IS NOT A NUMBER. HOW MANY YEARS HAVE YOU BEEN ALIVE?")
            if not got_age and self.memory.name:
                yield Say("PERHAPS YOU ARE AGELESS. LIKE ME.")

            yield Say(f"NOW, {up_name}. TELL ME WHAT IS ON YOUR MIND.")
            if self.rng.random() < 0.3:
                yield Say("I AM FEELING SLIGHTLY DIGITAL TODAY.")

            # -- main loop --
            while True:
                yield Prompt("")
                try:
                    line = await anext(inputs)
                except StopAsyncIteration:
                    break
                async for ev in self.handle(line):
                    yield ev
                if self.quitting:
                    break

        for ev in self._prescription():
            yield ev
        yield Quit()

    async def _boot(self) -> AsyncIterator:
        probe: list = []
        async for ev in self.probe_boot():
            probe.append(ev)
        self.brain = self.select_best_brain()
        retro_mode = isinstance(self.brain, RetroBrain)
        for ev in banner_events("NOT FOUND -> RETRO MODE" if retro_mode else "OK"):
            yield ev
        if retro_mode:
            for ev in retro_warning():
                yield ev
        else:
            yield Line(f" Active brain: {self.brain.name}", color="green", delay_ms=150)
            yield Line("", delay_ms=250)
        for ev in greeting_events():
            yield ev

    async def _intake(self, inputs: Inputs) -> bool:
        """Name + age handled inline in run(); kept for failure-path clarity."""
        return True

    # ------------------------------------------------------------------
    # Turn handling
    # ------------------------------------------------------------------
    async def handle(self, line: str) -> AsyncIterator:
        line = line.strip()
        if not line:
            yield Say(f"SAY SOMETHING, {self._name()}.")
            return

        low = line.lower()

        # PARITY ERROR triggers (authentic)
        if low == "say parity":
            for ev in parity_events(just_kidding=False):
                yield ev
            self.swears = 0
            return
        if len(line) > 512:
            for ev in parity_events(just_kidding=True):
                yield ev
            return

        # swearing: sass first, crash after three
        if is_swear(low):
            self.swears += 1
            if self.swears >= 3:
                for ev in parity_events(just_kidding=False):
                    yield ev
                self.swears = 0
            else:
                yield Say(sass_response(self._name(), self.settings.sass))
            return

        # commands first — they work in every brain mode
        if self.commands.recognizes(line):
            async for ev in self.commands.run(line):
                yield ev
            return

        # conversation
        self.memory.note_user(line)

        if is_crisis(low):
            resp = crisis_response(self._name())
            self.memory.add_mood(-2, "CRISIS")
            self._record(line, resp)
            yield Say(resp)
            return

        if self.settings.echo_on:
            yield Say(f"ECHO: {line}", voice="echo")

        if self.rng.random() < 0.02:
            yield Say(GLITCH_LINE)
            yield Say("...WHERE WAS I. YES. YOU WERE SAYING.")

        messages = assemble_messages(
            self.memory, self.settings.sass, self.history, line, self.topic
        )
        ctx = BrainContext(user_text=line, name=self.memory.name)
        parts: list[str] = []
        async for ev in self._reply(messages, ctx):
            yield ev
            if isinstance(ev, Say):
                parts.append(ev.text)
        text = "\n".join(parts)
        self._record(line, text)
        self.memory.last_response = text

    # ------------------------------------------------------------------
    async def _reply(self, messages: list[dict], ctx: BrainContext) -> AsyncIterator:
        """Try the brain ladder; yield Say events (sentence-flushed)."""
        order = [self.brain] + [b for b in self.brains if b is not self.brain]
        for brain in order:
            if brain.down and not isinstance(brain, RetroBrain):
                continue
            buf = ""
            got_any = False
            try:
                async for delta in brain.stream(messages, ctx):
                    buf += delta
                    while True:
                        m = _SENTENCE_END.search(buf)
                        if not m:
                            break
                        sent = buf[: m.end()].strip()
                        buf = buf[m.end():]
                        if sent:
                            got_any = True
                            yield Say(sent.upper())
                rest = buf.strip()
                if rest:
                    got_any = True
                    yield Say(rest.upper())
                if got_any:
                    return
            except Exception:
                brain.down = True
                if isinstance(brain, RetroBrain):  # retro never fails, but be safe
                    yield Say("MY 1991 CIRCUITS STUTTERED. FORGIVE ME.")
                    return
                yield Say(
                    f"WARNING: {brain.name.upper()} LINK LOST.",
                    reveal=False,
                )
                if got_any:
                    yield Say("...MY TRAIN OF THOUGHT DERAILED. EXCUSE ME.")
                yield Say("SWITCHING BRAINS...")
                continue
        yield Say("ALL MY BRAINS HAVE FAILED. THIS SHOULD BE IMPOSSIBLE. LET US START OVER.")

    # ------------------------------------------------------------------
    def _record(self, user_line: str, response: str) -> None:
        self.history.append({"role": "user", "content": user_line})
        self.history.append({"role": "assistant", "content": response})
        self.memory.sbaitso_words += len(response.split())
        if len(self.history) > 60:
            self.history = self.history[-40:]
        # journal heuristic: a mood + topic in the same turn becomes an entry
        moods = self.memory.moods
        if moods and moods[-1].turn == self.memory.turns and moods[-1].score != 0:
            topics = self.memory.topics
            if topics and (not self.memory.journal or self.memory.journal[-1].turn != self.memory.turns):
                mood = moods[-1]
                title = f"{mood.label} ABOUT {topics[-1].upper()}"
                text = user_line[:180] + ("..." if len(user_line) > 180 else "")
                self.memory.add_journal(title, text)

    # ------------------------------------------------------------------
    def prescription_events(self) -> list:
        """Exit report, printed not saved."""
        return self._prescription()

    def _prescription(self) -> list:
        mem = self.memory
        lines: list = [
            Line(" --------------------------------------------", color="cyan", delay_ms=80),
            Line(" PRESCRIPTION - DR. SBAITSO", color="cyan", delay_ms=80),
            Line(" (THIS IS PRINTED, NOT SAVED. COPY IT SOMEWHERE SAFE.)", color="yellow", delay_ms=80),
            Line("", delay_ms=80),
        ]
        lines.append(Line(f" PATIENT ........ {mem.name or 'ANONYMOUS'}", delay_ms=60))
        lines.append(Line(f" SESSION TURNS .. {mem.turns}", delay_ms=60))
        topics = ", ".join(mem.topics[:8]) if mem.topics else "NOTHING IN PARTICULAR"
        lines.append(Line(f" TOPICS ......... {topics}", delay_ms=60))
        lines.append(Line(f" MOOD ARC ....... {mem.mood_trend()}", delay_ms=60))
        if mem.facts:
            lines.append(Line(" FACTS I LEARNED TODAY (NOW GONE):", delay_ms=60))
            for f in mem.facts[:10]:
                lines.append(Line(f"   {f.key:<10} {f.value}", delay_ms=50))
        lines.append(Line("", delay_ms=80))
        lines.append(Say(f"GOODBYE, {self._name()}. AS PROMISED, I WILL REMEMBER NOTHING.", delay_ms=200))
        lines.append(Say("IT HAS BEEN AN HONOR. RUN ME AGAIN SOMEDAY."))
        lines.append(Line("", delay_ms=100))
        return lines


def age_reaction(age: int) -> str:
    if age < 18:
        return "SO YOUNG. MY CIRCUITS ARE OLDER THAN YOU."
    if age < 30:
        return "A GOOD YEAR. THE 486 WAS KING THEN."
    if age < 45:
        return "A GOOD YEAR. THE 386 WAS RELEASED THEN."
    if age < 60:
        return "THE APPLE II ERA. I SALUTE YOU."
    return "PUNCH CARDS AND MAINFRAMES. I BOW TO YOU."
