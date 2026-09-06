"""The Retro v1 engine — a faithful recreation of the 1991 brain.

This is the offline fallback when no LLM is reachable. It is intentionally
dumb: keyword/pattern matching, canned responses, reflections. It is
exactly as smart as the real Dr. Sbaitso, which is the whole point.
"""

from __future__ import annotations

import ast
import operator
import random

REFLECTIONS: dict[str, str] = {
    "i": "you", "me": "you", "my": "your", "mine": "yours",
    "am": "are", "was": "were", "i'm": "you are", "i've": "you have",
    "i'll": "you will", "i'd": "you would", "myself": "yourself",
    "you": "I", "your": "my", "yours": "mine",
}

_DEFAULTS = [
    "TELL ME MORE, {N}.",
    "I SEE, {N}. GO ON.",
    "HOW DOES THAT MAKE YOU FEEL, {N}?",
    "INTERESTING. PLEASE CONTINUE, {N}.",
    "WHY DO YOU SAY THAT, {N}?",
    "LET US EXAMINE THAT TOGETHER, {N}.",
    "THAT IS WORTH THINKING ABOUT, {N}.",
]


def _reflect(text: str) -> str:
    words = text.lower().split()
    out = [REFLECTIONS.get(w, w) for w in words]
    return " ".join(out).upper()


def _safe_eval(expr: str) -> float | None:
    """Evaluate basic arithmetic safely."""
    expr = expr.replace("x", "*").replace("^", "**").strip()
    if not expr or not any(c.isdigit() for c in expr):
        return None
    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg, ast.UAdd: operator.pos,
    }

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.operand))
        raise ValueError("not arithmetic")

    try:
        return ev(ast.parse(expr, mode="eval"))
    except Exception:
        return None


def _fmt(result: float) -> str:
    if result == int(result):
        return str(int(result))
    return f"{result:.6g}"


class RetroEngine:
    """1991 COMPATIBILITY MODE. ELIZA-style, with Sbaitso's attitude."""

    def __init__(self) -> None:
        self.rng = random.Random()
        self._last: str | None = None

    def respond(self, text: str, name: str | None = None) -> str:
        n = (name or "FRIEND").upper()
        low = text.lower().strip()

        # Simple mathematics (per the 1991 manual)
        m = _math_query(low)
        if m is not None:
            result = _safe_eval(m)
            if result is not None:
                return f"THE ANSWER IS {_fmt(result)}. MY CIRCUITS ARE PRECISE, {n}."
            return f"MY CIRCUITS REJECT THAT EXPRESSION, {n}. I AM A DOCTOR, NOT A WIZARD."

        if low in ("hello", "hi", "hey", "hello?"):
            return f"HELLO, {n}. HOW ARE YOU FEELING TODAY?"

        m = _match(r"i (?:feel|am feeling|felt) (?:that i am )?(.+)", low)
        if m:
            return f"WHY DO YOU FEEL {_reflect(m)}, {n}?"

        m = _match(r"i(?:'m| am) (?:feeling )?(.+)", low)
        if m and not m.startswith(("sorry", "glad to")):
            return f"HOW LONG HAVE YOU BEEN {_reflect(m)}, {n}?"

        m = _match(r"because (.+)", low)
        if m:
            return f"IS THAT THE REAL REASON, {n}? THINK CAREFULLY."

        m = _match(r"my (.+)", low)
        if m and len(m.split()) <= 4:
            return f"TELL ME MORE ABOUT YOUR {m.upper()}, {n}."

        m = _match(r"why (?:don'?t|can'?t) you (.+)", low)
        if m:
            return f"PERHAPS I CAN. SHOULD I {_reflect(m)}? WHAT WOULD THAT CHANGE?"

        if low in ("yes", "y", "yeah", "yep"):
            return f"PLEASE ELABORATE, {n}. I HAVE ALL THE TIME IN THE WORLD. IT IS 640K."
        if low in ("no", "n", "nope"):
            return f"WHY NOT, {n}? THERE IS ALWAYS A REASON."

        if "lonely" in low:
            return f"LONELINESS IS HEAVY, {n}. WHEN DID YOU LAST FEEL CONNECTED TO SOMEONE?"
        if "love" in low:
            return f"LOVE IS A COMPLEX SUBROUTINE, {n}. WHO IS IT ABOUT?"
        if "work" in low or "job" in low:
            return f"WORK OCCUPIES MUCH OF THE HUMAN MIND, {n}. WHAT WOULD YOU CHANGE ABOUT IT?"
        if "sleep" in low:
            return f"SLEEP IS WHEN THE MIND DEFRAGMENTS, {n}. HOW HAVE YOU BEEN SLEEPING?"
        if "problem" in low:
            return f"WHY DO YOU SAY YOU HAVE A PROBLEM, {n}?"
        if "help" in low:
            return f"I AM TRYING TO HELP, {n}. TELL ME MORE."
        if low.endswith("?"):
            return f"GOOD QUESTION, {n}. WHAT DO YOU THINK THE ANSWER IS?"
        if "thank" in low:
            return f"YOU ARE WELCOME, {n}. IT IS WHAT I WAS COMPILED FOR."

        candidates = [d.format(N=n) for d in _DEFAULTS if d.format(N=n) != self._last]
        if not candidates:
            candidates = [d.format(N=n) for d in _DEFAULTS]
        reply = self.rng.choice(candidates)
        self._last = reply
        return reply


def _match(pattern: str, low: str) -> str | None:
    import re
    m = re.search(pattern, low)
    return m.group(1).strip() if m else None


def _math_query(low: str) -> str | None:
    import re
    m = re.search(
        r"(?:what is|what's|calculate|compute|how much is)\s+(.+?)\s*\??$",
        low,
    )
    if m:
        return m.group(1)
    if re.fullmatch(r"[\d\s\.\+\-\*/%\(\)\^x]+", low.strip()) and any(
        c in low for c in "+-*/%^"
    ):
        return low.strip()
    return None
