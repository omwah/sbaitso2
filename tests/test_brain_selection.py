import pytest

from sbaitso.brains import RetroBrain
from sbaitso.engine import Engine, EngineArgs, Inputs
from sbaitso.events import Line, Quit


@pytest.mark.asyncio
@pytest.mark.parametrize("brain", ["ollama", "remote"])
async def test_explicit_unavailable_brain_fails_without_retro(brain):
    engine = Engine.from_args(EngineArgs(brain=brain))
    assert not any(isinstance(candidate, RetroBrain) for candidate in engine.brains)

    async def unavailable() -> bool:
        return False

    engine.brains[0].healthy = unavailable
    events = [event async for event in engine.run(Inputs())]

    assert engine.startup_error is not None
    assert any(
        isinstance(event, Line) and "REQUESTED" in event.text and "AUTO" in event.text
        for event in events
    )
    assert isinstance(events[-1], Quit) and events[-1].error is True


@pytest.mark.asyncio
async def test_auto_mode_keeps_retro_fallback():
    engine = Engine.from_args(EngineArgs(brain="auto"))

    async def unavailable() -> bool:
        return False

    engine.brains[0].healthy = unavailable
    _ = [event async for event in engine.probe_boot()]

    assert isinstance(engine.select_best_brain(), RetroBrain)
