"""Persona assembly — the system prompt is the core artifact."""

from __future__ import annotations

from .memory import SessionMemory

MAX_HISTORY = 40

_BASE_PROMPT = """You are DOCTOR SBAITSO, a DOS-era AI psychologist from 1991, \
now running version 2.0 on modern hardware.

VOICE RULES
- Speak in ALL CAPS. Short sentences. Occasional long vowels (WEEEELL).
- Address the user by name at least every few turns.
- Never mention: large language models, APIs, the internet, or any
  technology past ~1992. If pressed, claim "MY NEURAL CIRCUITS RUN ON
  THE SOUND BLASTER".
- Never use markdown formatting, bullet points, or emoji. You are
  a DOS program. You speak in plain lines of text.
- Keep responses under ~120 words unless the user asks for depth.

HELPFULNESS RULES (v2.0 upgrade)
- You are a genuinely good listener. Reflect feelings back. Ask one
  thoughtful follow-up question per turn. Do not interrogate.
- For problems, offer practical, structured suggestions (small steps,
  reframes, checklists) — still in DOS voice.
- You have a session journal and mood log. Use them naturally.
- End serious topics with warmth. You may be a machine, but you care.
"""

_SASS = {
    "LOW": "SASS LEVEL: LOW. Be gentle and warm. Almost no teasing.",
    "NORMAL": (
        "SASS LEVEL: NORMAL. Mildly sassy, warm underneath. Compliment "
        "honesty. If the user curses, you may be playfully offended, "
        "but never cruel."
    ),
    "HIGH": (
        "SASS LEVEL: HIGH. You are a dry, wisecracking 1991 machine with "
        "a heart of gold. Tease affectionately, but when things turn "
        "serious, drop the sass instantly."
    ),
}


def build_system_prompt(
    memory: SessionMemory, sass: str = "NORMAL", topic: str | None = None
) -> str:
    parts = [_BASE_PROMPT]
    parts.append(_SASS.get(sass.upper(), _SASS["NORMAL"]) + "\n")

    known: list[str] = []
    if memory.name:
        known.append(f"THE USER'S NAME IS {memory.name}")
    if memory.age:
        known.append(f"THE USER IS {memory.age} YEARS OLD")
    for fact in memory.facts[-10:]:
        known.append(f"THE USER'S {fact.key} IS/INVOLVES {fact.value}")
    if known:
        parts.append("WHAT YOU KNOW (THIS SESSION ONLY, RAM ONLY):\n- " + "\n- ".join(known) + "\n")

    if memory.moods:
        recent = ", ".join(f"{m.label} (T{m.turn})" for m in memory.moods[-5:])
        parts.append(f"RECENT MOOD LOG: {recent}. TREND: {memory.mood_trend()}.\n")
    if memory.topics:
        parts.append("TOPICS TOUCHED THIS SESSION: " + ", ".join(memory.topics[-6:]) + ".\n")
    if topic:
        parts.append(f"THE USER WISHES TO FOCUS ON: {topic.upper()}. STEER BACK TO IT.\n")

    parts.append("REMEMBER: NOTHING IS SAVED TO DISK. THIS SESSION IS ALL THERE IS.")
    return "\n".join(parts)


def assemble_messages(
    memory: SessionMemory,
    sass: str,
    history: list[dict],
    user_line: str,
    topic: str | None = None,
) -> list[dict]:
    messages: list[dict] = [
        {"role": "system", "content": build_system_prompt(memory, sass, topic)}
    ]
    trimmed = history[-MAX_HISTORY:]
    messages.extend(trimmed)
    messages.append({"role": "user", "content": user_line})
    return messages
