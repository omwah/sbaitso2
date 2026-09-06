from sbaitso.brains import BrainContext, OllamaBrain
from sbaitso.engine import Engine, EngineArgs
from sbaitso.events import Say


class ChunkedOllama(OllamaBrain):
    """An Ollama-shaped test brain so the engine takes its streaming path."""

    def __init__(self) -> None:
        self.name = "TEST OLLAMA"
        self.down = False

    async def stream(self, messages, ctx):
        yield "FIRST. THIS  IS  WIDE.  "
        yield " SECOND.  THIRD. "


async def streamed_say_texts(strip_boundaries: bool) -> list[str]:
    brain = ChunkedOllama()
    engine = Engine(
        [brain],
        EngineArgs(
            brain="ollama",
            strip_response_boundary_whitespace=strip_boundaries,
        ),
    )
    engine.brain = brain
    events = [
        event async for event in engine._reply([], BrainContext(user_text="HELLO"))
    ]
    return [event.text for event in events if isinstance(event, Say) and event.text]


async def test_streaming_collapses_extra_whitespace_for_all_frontends():
    assert await streamed_say_texts(True) == [
        "FIRST. ",
        "THIS IS WIDE. ",
        "SECOND. ",
        "THIRD. ",
    ]


async def test_boundary_space_stripping_can_be_disabled_in_engine_args():
    assert await streamed_say_texts(False) == [
        "FIRST. ",
        "THIS  IS  WIDE. ",
        "  SECOND. ",
        " THIRD. ",
    ]
