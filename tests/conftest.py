"""Shared fixtures: a retro-only engine (no network)."""

import pytest

from sbaitso.engine import Engine, EngineArgs
from sbaitso.events import Say


@pytest.fixture
def engine():
    args = EngineArgs(brain="retro")
    eng = Engine.from_args(args)
    eng.memory.name = "MIKE"
    return eng


async def events_of(engine, line):
    """Run one handle() turn and collect events."""
    return [ev async for ev in engine.handle(line)]


def says_of(events):
    """All doctor speech text from an event list."""
    return [ev.text for ev in events if isinstance(ev, Say)]
