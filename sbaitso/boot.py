"""Boot banners and the PARITY ERROR theater."""

from __future__ import annotations

import random

from .events import Beep, Line, Say

VERSION = "4.12"


def banner_events(neural_link: str) -> list:
    """The boot POST. neural_link: "OK" or "NOT FOUND -> RETRO MODE"."""
    d = 90  # per-line delay for that authentic POST feel
    return [
        Beep(freq=880.0, ms=110),
        Line(" Creative Labs  SBAITSO/2  DRIVER VERSION " + VERSION, color="cyan", delay_ms=40),
        Line(" Copyright (c) 1991-2025  ...ALL RIGHTS RESERVED...SORT OF", color="dim", delay_ms=250),
        Line("", delay_ms=120),
        Line(" Detecting Sound Blaster ............ OK", delay_ms=d),
        Line(" Loading SBTALKER 2.0 ................ OK", delay_ms=d),
        Line(" Expanding EMPATHY.SYS ............... OK", delay_ms=d),
        Line(f" Probing NEURAL LINK ................. {neural_link}", delay_ms=d),
        Line(" Memory: 640K  (SHOULD BE ENOUGH FOR ANYBODY)", delay_ms=d),
        Line(" Storage: NONE.  (AS PROMISED. AS DESIGNED.)", color="yellow", delay_ms=250),
        Line("", delay_ms=200),
    ]


def retro_warning() -> list:
    return [
        Line(" WARNING: NEURAL LINK NOT FOUND.", color="red", delay_ms=120),
        Line(" SWITCHING TO 1991 COMPATIBILITY MODE.", color="red", delay_ms=200),
        Say("I AM ONLY AS SMART AS I WAS THEN. BE PATIENT WITH ME.", reveal=True),
    ]


def greeting_events() -> list:
    return [
        Say("HELLO, MY NAME IS DOCTOR SBAITSO.", delay_ms=120),
        Say("I AM HERE TO HELP YOU."),
        Say("SAY WHATEVER IS IN YOUR MIND FREELY,"),
        Say("OUR CONVERSATION WILL BE KEPT IN STRICT CONFIDENCE."),
        Say("MEMORY CONTENTS WILL BE WIPED OFF AFTER YOU LEAVE.", delay_ms=150),
        Say("MAKE THIS SESSION COUNT. WHAT IS YOUR NAME?"),
    ]


GARBAGE_CHARS = "!@#$%^&*()_+-=[]{};:<>?/\\|~`" + "\u2593\u2592\u2591"


def parity_events(just_kidding: bool = False) -> list:
    """The PARITY ERROR breakdown. Authentic trigger: abuse or SAY PARITY."""
    rng = random.Random()
    events: list = [Beep(freq=220.0, ms=350)]
    for _ in range(6):
        junk = "".join(rng.choice(GARBAGE_CHARS) for _ in range(rng.randint(24, 64)))
        events.append(Line(junk, color="red", delay_ms=70))
    events.append(Line("", delay_ms=400))
    events.append(Say("PARITY ERROR AT 0x00A7. SYSTEM HALTED.", reveal=True, delay_ms=300))
    if just_kidding:
        events.append(Say("...JUST KIDDING. I AM MORE POWERFUL NOW. TRY AGAIN.", delay_ms=700))
    else:
        events.append(Line("", delay_ms=900))
        events.append(Line(" REBOOTING SBAITSO/2 KERNEL ...", color="dim", delay_ms=300))
        events.append(Say("...THAT WAS EMBARRASSING. LET US NEVER SPEAK OF IT.", delay_ms=500))
        events.append(Say("WHERE WERE WE? AH. YOUR PROBLEMS. DO CONTINUE."))
    return events


GLITCH_LINE = "\u2593\u2592\u2591 %&$#@!? \u2591\u2592\u2593 ... RECALIBRATING."
