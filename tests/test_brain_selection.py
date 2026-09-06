import json

import pytest

from sbaitso.brains import RetroBrain
from sbaitso.engine import Engine, EngineArgs, Inputs
from sbaitso.events import Line, Quit, Say


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("brain", "extra_args", "expected_model"),
    [
        ("ollama", {"model": "debug-ollama"}, "debug-ollama"),
        ("remote", {"remote_model": "debug-remote"}, "debug-remote"),
    ],
)
async def test_debug_llm_emits_outbound_payload_without_headers(
    brain, extra_args, expected_model
):
    engine = Engine.from_args(
        EngineArgs(brain=brain, debug_llm=True, **extra_args)
    )
    engine.memory.name = "MIKE"

    async def reply(messages, context):
        yield "DEBUG RESPONSE."

    engine.brains[0].stream = reply
    events = [event async for event in engine.handle("I FEEL STUCK.")]
    payload_line = next(
        event for event in events
        if isinstance(event, Line) and event.text.startswith("{")
    )
    payload = json.loads(payload_line.text)

    assert payload["model"] == expected_model
    assert payload["stream"] is True
    assert payload["messages"][-1] == {"role": "user", "content": "I FEEL STUCK."}
    assert "authorization" not in payload_line.text.lower()
    assert "api_key" not in payload_line.text.lower()


@pytest.mark.asyncio
async def test_llm_deltas_render_partially_then_speak_complete_sentence():
    engine = Engine.from_args(EngineArgs(brain="ollama", model="stream-test"))
    engine.rng.seed(0)  # avoid the intentional 2% glitch interjection
    engine.memory.name = "MIKE"

    async def reply(messages, context):
        yield "THIS IS A STREAMED "
        yield "RESPONSE THAT ARRIVES "
        yield "IN PIECES."

    engine.brains[0].stream = reply
    events = [event async for event in engine.handle("SHOW ME PROGRESS.")]
    says = [event for event in events if isinstance(event, Say)]

    content_says = [event for event in says if event.text]
    assert any(event.partial for event in content_says)
    assert "".join(event.text for event in content_says) == (
        "THIS IS A STREAMED RESPONSE THAT ARRIVES IN PIECES."
    )
    assert all(event.line_end is False for event in content_says)
    assert says[-1].text == "" and says[-1].line_end is True
    final = content_says[-1]
    assert final.partial is False
    assert final.speech_text == "THIS IS A STREAMED RESPONSE THAT ARRIVES IN PIECES."


@pytest.mark.asyncio
async def test_streaming_preserves_space_after_a_completed_sentence():
    engine = Engine.from_args(EngineArgs(brain="ollama", model="stream-test"))
    engine.rng.seed(0)
    engine.memory.name = "MIKE"

    async def reply(messages, context):
        yield "A COMPLETE FIRST SENTENCE. "
        yield "A SECOND SENTENCE."

    engine.brains[0].stream = reply
    events = [event async for event in engine.handle("SHOW ME SPACING.")]
    displayed = "".join(
        event.text for event in events if isinstance(event, Say) and event.text
    )

    assert "SENTENCE. A SECOND" in displayed
