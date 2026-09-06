from sbaitso.boot import greeting_events
from sbaitso.events import Say


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
