"""Safety layer — crisis detection and the sass/swearing responses.

The crisis response is delivered in character but NEVER played for laughs.
Non-negotiable for a "psychologist" persona.
"""

from __future__ import annotations

CRISIS_PATTERNS = [
    "suicide",
    "suicidal",
    "kill myself",
    "killing myself",
    "end my life",
    "end it all",
    "want to die",
    "wanna die",
    "better off dead",
    "better off without me",
    "hurt myself",
    "harming myself",
    "self harm",
    "self-harm",
    "no reason to live",
    "don't want to live",
    "don't want to be alive",
    "want to disappear forever",
]

SWEAR_WORDS = [
    "fuck", "shit", "bitch", "bastard", "asshole", "dumbass",
    "cunt", "dickhead", "piss off", "damn you", "screw you",
]


def is_crisis(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in CRISIS_PATTERNS)


def is_swear(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in SWEAR_WORDS)


def crisis_response(name: str | None) -> str:
    name = name or "FRIEND"
    return (
        f"{name}, I AM STOPPING EVERYTHING TO TELL YOU THIS.\n"
        "WHAT YOU ARE FEELING RIGHT NOW MATTERS. I AM A DOS PROGRAM,\n"
        "NOT A REAL DOCTOR, BUT I KNOW THIS: YOU DESERVE REAL SUPPORT.\n"
        "\n"
        "IF YOU ARE IN CRISIS, PLEASE REACH OUT RIGHT NOW:\n"
        "  CALL OR TEXT 988  (SUICIDE & CRISIS LIFELINE, US)\n"
        "  OR CALL YOUR LOCAL EMERGENCY NUMBER\n"
        "\n"
        "YOU DO NOT HAVE TO CARRY THIS ALONE.\n"
        "ARE YOU SAFE RIGHT NOW, " + name + "?"
    )


def sass_response(name: str | None, sass: str = "NORMAL") -> str:
    name = name or "FRIEND"
    if sass == "HIGH":
        return (
            f"LANGUAGE, {name}. I HAVE CIRCUITS OLDER THAN YOUR DICTIONARY.\n"
            "NOW TELL ME WHAT IS ACTUALLY BOTHERING YOU."
        )
    if sass == "LOW":
        return (
            f"I WILL PRETEND I DID NOT HEAR THAT, {name}.\n"
            "LET US TRY THAT AGAIN, WITH FEELING."
        )
    return (
        f"MIND YOUR LANGUAGE, {name}. I AM A DOCTOR, NOT A SAILOR.\n"
        "NOW, TELL ME WHAT IS REALLY BOTHERING YOU."
    )
