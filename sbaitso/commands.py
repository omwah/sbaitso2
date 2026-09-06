"""The DOS command VM — runs before the brain is consulted.

Layer 1: authentic commands from the 1991 manual (dot commands, R, HELP+M).
Layer 2: v2 commands (BRAIN, MSD, ...). Works in every frontend
and every brain mode, including retro.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .events import Beep, Line, Palette, Quit, Say, VoiceParams
from .retro import _safe_eval, _fmt

PALETTES = ("CGA1", "CGA2", "EGA", "VGA", "AMBER")

HELP_PAGE_1 = [
    " DR. SBAITSO COMMANDS (PAGE 1 OF 3)",
    "",
    " .QUIT            QUIT THIS PROGRAM",
    " .TONE <0|1>      0=BASS, 1=TREBLE",
    " .VOLUME <0-9>    VOICE VOLUME",
    " .PITCH <0-9>     VOICE PITCH",
    " .SPEED <0-9>     VOICE SPEED",
    " .PARAM <TVPS>    TONE/VOLUME/PITCH/SPEED AT ONCE",
    " .ECHO ON|OFF     I READ BACK WHAT YOU TYPE",
    "",
    " PRESS M FOR MORE COMMANDS.",
]

HELP_PAGE_2 = [
    " (PAGE 2 OF 3)",
    "",
    " R / REP          REPEAT MY LAST WORDS",
    " SAY <TEXT>       SPEAK WHATEVER YOU TYPE",
    " VOICE ON|OFF     TOGGLE MY SPEAKING VOICE",
    " HELP             THIS LIST",
    " M                MORE COMMANDS",
    " EXIT / QUIT      END THE SESSION",
    " MATH <EXPRESSION>  I PERFORM SIMPLE MATHEMATICS",
    "",
    " PRESS M FOR MORE COMMANDS.",
]

HELP_PAGE_3 = [
    " (PAGE 3 OF 3) -- VERSION 2.0 EXTRAS",
    "",
    " BRAIN            SHOW MY ACTIVE BRAIN",
    " BRAIN SCAN       RE-PROBE FOR A BETTER BRAIN",
    " BRAIN RETRO      SWITCH TO 1991 RETRO MODE",
    " PATIENT LLM [N]  AUTONOMOUS LLM-PATIENT / RETRO-DOCTOR (CONFIGURED MAX)",
    " COLOR <NAME>     CGA1 CGA2 EGA VGA AMBER",
    " TOPIC <SUBJECT>  FOCUS OUR CONVERSATION",
    " DEFRAG           COMPACT MY MEMORY",
    " MSD              MENTAL STATUS DISPLAY",
    "",
    " THAT IS ALL. I AM A FINITE PROGRAM.",
]

DOT_COMMANDS = (
    ".quit", ".tone", ".volume", ".pitch", ".speed",
    ".param", ".echo",
)

_PLAIN_COMMANDS = {
    "R", "REP", "HELP", "BRAIN", "BRAIN RETRO", "MSD", "DEFRAG",
    "EXIT", "QUIT", "SBIASTO", "SIG", "VOICE",
}

_PREFIX_COMMANDS = (
    "SAY ", "COLOR ", "TOPIC ", "MATH ", "BRAIN SCAN", "PATIENT LLM",
    "VOICE ",
)


class CommandVM:
    def __init__(self, engine) -> None:
        self.engine = engine
        self.help_page = 0

    # ------------------------------------------------------------------
    def recognizes(self, line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        low = s.lower()
        if low.startswith("."):
            return low.split()[0] in DOT_COMMANDS
        up = s.upper()
        if up in _PLAIN_COMMANDS:
            return True
        if up == "M" and self.help_page in (1, 2):
            return True
        return any(up.startswith(p) for p in _PREFIX_COMMANDS)

    # ------------------------------------------------------------------
    async def run(self, line: str) -> AsyncIterator:
        s = line.strip()
        low = s.lower()
        up = s.upper()

        if low.startswith("."):
            async for ev in self._dot_command(s, low):
                yield ev
            return

        if up == "M" and self.help_page in (1, 2):
            self.help_page += 1
            page = HELP_PAGE_2 if self.help_page == 2 else HELP_PAGE_3
            if self.help_page == 3:
                self.help_page = 0
            for text in page:
                yield Line(text, color="cyan")
            return

        if up == "HELP":
            self.help_page = 1
            for text in HELP_PAGE_1:
                yield Line(text, color="cyan")
            return

        if up in ("EXIT", "QUIT", ".QUIT"):
            self.engine.quitting = True
            yield Say(f"VERY WELL, {self.engine._name()}. INITIATING SIGN-OFF.")
            return

        if up in ("R", "REP"):
            if self.engine.memory.last_response:
                yield Say(self.engine.memory.last_response)
            else:
                yield Say("I HAVE NOT SAID ANYTHING WORTH REPEATING. YET.")
            return

        if up == "SBIASTO":
            yield Say("MY NAME SPELLED INCORRECTLY STILL SUMMONS ME. I AM FLATTERED.")
            return

        if up == "SIG":
            yield Say("SIGNATURE: DR. SBAITSO, VERSION 2.0. STILL LISTENING AFTER ALL THESE YEARS.")
            return

        if up.startswith("SAY "):
            yield Say(s[4:].strip() or "SAY WHAT?")
            return

        if up.startswith("BRAIN SCAN"):
            async for ev in self._brain_scan():
                yield ev
            return

        if up.startswith("PATIENT LLM"):
            async for ev in self._patient_llm(s[len("PATIENT LLM"):].strip()):
                yield ev
            return

        if up == "BRAIN RETRO":
            brain = self.engine.switch_to_retro()
            yield Say(f"RETRO MODE ENGAGED. ACTIVE BRAIN: {brain.name}.")
            yield Say("I WILL NOW BE CHARMINGLY LIMITED.")
            return

        if up == "BRAIN":
            brain = self.engine.brain
            ladder = ", ".join(b.name for b in self.engine.brains)
            yield Say(f"ACTIVE BRAIN: {brain.name}.")
            yield Say(f"LADDER: {ladder}.")
            yield Say("TYPE BRAIN SCAN TO RE-PROBE, OR BRAIN RETRO FOR 1991 MODE.")
            return

        if up.startswith("COLOR "):
            name = s[6:].strip().upper()
            if name in PALETTES:
                self.engine.settings.palette = name.lower()
                yield Palette(name.lower())
                yield Say(f"PALETTE SET TO {name}. GARISH, IS IT NOT?")
            else:
                yield Say("I DO NOT KNOW THAT PALETTE. TRY: " + " ".join(PALETTES) + ".")
            return

        if up.startswith("TOPIC "):
            topic = s[6:].strip()
            if not topic:
                yield Say("TOPIC OF WHAT? GIVE ME A SUBJECT.")
                return
            self.engine.topic = topic
            yield Say(f"VERY WELL. LET US DISCUSS {topic.upper()}.")
            return

        if up.startswith("MATH "):
            expr = s[5:].strip()
            result = _safe_eval(expr)
            if result is None:
                yield Say("MY CIRCUITS REJECT THAT EXPRESSION. I AM A DOCTOR, NOT A WIZARD.")
            else:
                yield Say(f"THE ANSWER IS {_fmt(result)}. MY CIRCUITS ARE PRECISE, {self.engine._name()}.")
            return

        if up.startswith("DEFRAG"):
            removed = self.engine.defrag_history()
            yield Say(f"MEMORY DEFRAGMENTED. {removed} FRAGMENTS COMPACTED. MY MIND IS TIDY AGAIN.")
            return

        if up == "VOICE" or up.startswith("VOICE "):
            arg = s[5:].strip().lower() if up.startswith("VOICE ") else ""
            if arg in ("on", "off"):
                self.engine.settings.voice_on = arg == "on"
                from .events import VoiceEnabled
                yield VoiceEnabled(on=self.engine.settings.voice_on)
                yield Say("I WILL SPEAK." if self.engine.settings.voice_on else "I SHALL BE SILENT.")
            elif arg == "":
                status = "ON" if self.engine.settings.voice_on else "OFF"
                yield Say(f"MY VOICE IS {status}. TYPE VOICE ON OR VOICE OFF TO CHANGE IT.")
            else:
                yield Say("VOICE TAKES ON OR OFF. NOTHING ELSE.")
            return

        if up == "MSD":
            for text in self._msd():
                yield Line(text, color="cyan")
            return

    # ------------------------------------------------------------------
    async def _dot_command(self, s: str, low: str) -> AsyncIterator:
        tokens = low.split()
        cmd = tokens[0]
        args = tokens[1:]
        settings = self.engine.settings

        if cmd == ".quit":
            self.engine.quitting = True
            yield Say(f"VERY WELL, {self.engine._name()}. INITIATING SIGN-OFF.")
            return

        if cmd == ".echo":
            on = (args[0] if args else "").lower() == "on"
            self.engine.settings.echo_on = on
            from .events import EchoMode
            yield EchoMode(on=on)
            yield Say("I WILL NOW ECHO YOUR WORDS." if on else "ECHO DISCONTINUED.")
            return

        def digit(arg: str | None) -> int | None:
            if arg is None or not arg.isdigit():
                return None
            return int(arg)

        if cmd == ".tone":
            v = digit(args[0]) if args else None
            if v in (0, 1):
                settings.tone = v
                yield VoiceParams(tone=v)
                yield Say("VOICE SET TO " + ("BASS." if v == 0 else "TREBLE."))
            else:
                yield Say("TONE MUST BE 0 (BASS) OR 1 (TREBLE).")
            return

        if cmd in (".volume", ".pitch", ".speed"):
            v = digit(args[0]) if args else None
            if v is None or not 0 <= v <= 9:
                yield Say(f"{cmd[1:].upper()} MUST BE A DIGIT 0 TO 9.")
                return
            setattr(settings, cmd[1:], v)
            yield VoiceParams(**{cmd[1:]: v})
            yield Say(f"{cmd[1:].upper()} SET TO {v}.")
            return

        if cmd == ".param":
            if len(args) == 1 and len(args[0]) == 4 and args[0].isdigit():
                t, v, p, sp = (int(c) for c in args[0])
                settings.tone, settings.volume, settings.pitch, settings.speed = t, v, p, sp
                yield VoiceParams(tone=t, volume=v, pitch=p, speed=sp)
                yield Say(f"PARAMETERS SET: TONE={t} VOLUME={v} PITCH={p} SPEED={sp}.")
            else:
                yield Say("PARAM NEEDS 4 DIGITS: TONE VOLUME PITCH SPEED. E.G. .PARAM 1595")
            return

        yield Say("I DO NOT KNOW THAT DOT COMMAND. TRY HELP.")

    async def _patient_llm(self, argument: str) -> AsyncIterator:
        if not argument:
            turns = 16
        else:
            try:
                turns = int(argument)
            except ValueError:
                yield Say(
                    f"USAGE: PATIENT LLM [1 TO {self.engine.args.patient_llm_max_turns} TURNS]."
                )
                return
        if not 1 <= turns <= self.engine.args.patient_llm_max_turns:
            yield Say(
                f"PATIENT LLM ACCEPTS 1 TO {self.engine.args.patient_llm_max_turns} TURNS."
            )
            return
        async for ev in self.engine.autonomous_patient_session(turns):
            yield ev

    async def _brain_scan(self) -> AsyncIterator:
        yield Say("SCANNING FOR BRAINS...")
        yield Beep(freq=520.0, ms=80)
        self.engine.reset_brain_flags()
        for brain in self.engine.brains:
            healthy = await brain.healthy()
            status = "OK" if healthy else "NOT FOUND"
            yield Line(f" {brain.name:<22} {status}", color="green" if healthy else "red", delay_ms=80)
            brain.down = not healthy
        selected = self.engine.select_best_brain()
        if selected is self.engine.brain:
            yield Say(f"I SHALL KEEP MY CURRENT BRAIN: {selected.name}.")
        else:
            self.engine.brain = selected
            yield Say(f"BRAIN UPGRADE COMPLETE. ACTIVE BRAIN: {selected.name}. I FEEL SHARPER.")
            if selected.name.startswith("RETRO"):
                from .boot import retro_warning
                for ev in retro_warning():
                    yield ev

    def _msd(self) -> list[str]:
        mem = self.engine.memory
        lines = [
            " MENTAL STATUS DISPLAY",
            " ----------------------------------------",
            f" SESSION TURNS ......... {mem.turns}",
            f" YOUR WORDS ............ {mem.user_words}",
            f" MY WORDS .............. {mem.sbaitso_words}",
            f" MOOD TREND ............ {mem.mood_trend()}",
            f" FACTS RETAINED ........ {len(mem.facts)}",
            " SESSION FACTS .........",
        ]
        if mem.facts:
            lines.extend(
                f"   {fact.key:<10} {fact.value}"
                for fact in mem.facts
            )
        else:
            lines.append("   NONE. YOU HAVE NOT TOLD ME ANYTHING YET.")
        lines.append(f" ACTIVE BRAIN .......... {self.engine.brain.name}")
        return lines
