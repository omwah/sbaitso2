"""Shared DOS terminal layout rules for native and Textual frontends."""

from __future__ import annotations

import textwrap

SAY_WRAP_WIDTH = 72
RESPONSE_INDENT = " "


def wrap_terminal_line(text: str, width: int) -> list[str]:
    """Wrap a listing at word boundaries without splitting words."""
    if not text:
        return [""]
    return textwrap.wrap(
        text,
        width=max(1, width),
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]
