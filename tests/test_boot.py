import pytest

from sbaitso.boot import greeting_events, retro_warning
from sbaitso.engine import Engine, EngineArgs, Inputs
from sbaitso.events import Line, Say


def test_retro_warning_has_a_blank_line_before_the_doctor_speaks():
    events = retro_warning()
    assert isinstance(events[2], Line) and events[2].text == ""
    assert isinstance(events[3], Say)


def test_greeting_formats_as_one_wrapped_response():
    events = greeting_events()
    says = [event for event in events if isinstance(event, Say)]

    assert len(says) == 6
    assert all(event.line_end is False for event in says[:-1])
    assert says[-1].line_end is True
    assert "".join(event.text for event in says) == (
        "HELLO, MY NAME IS DOCTOR SBAITSO. I AM HERE TO HELP YOU. "
        "SAY WHATEVER IS IN YOUR MIND FREELY, "
        "OUR CONVERSATION WILL BE KEPT IN STRICT CONFIDENCE. "
        "MEMORY CONTENTS WILL BE WIPED OFF AFTER YOU LEAVE. "
        "MAKE THIS SESSION COUNT. WHAT IS YOUR NAME?"
    )


@pytest.mark.asyncio
async def test_age_reaction_and_handoff_share_one_wrapped_response():
    engine = Engine.from_args(EngineArgs(brain="retro"))
    engine.rng.seed(0)  # omit the optional digital aside
    inputs = Inputs()
    inputs.push("MIKE")
    inputs.push("42")
    inputs.close()
    events = [event async for event in engine.run(inputs)]
    says = [event for event in events if isinstance(event, Say)]

    age = next(event for event in says if event.text.startswith("A GOOD YEAR."))
    handoff = next(event for event in says if event.text.startswith("NOW, MIKE."))
    assert age.line_end is False and age.text.endswith(" ")
    assert handoff.line_end is True
    assert (age.text + handoff.text).startswith(
        "A GOOD YEAR. THE 386 WAS RELEASED THEN. NOW, MIKE."
    )
