from sbaitso.safety import crisis_response, is_crisis, is_swear

from conftest import events_of, says_of


def test_crisis_detection():
    assert is_crisis("I want to kill myself")
    assert is_crisis("thinking about suicide")
    assert is_crisis("i want to disappear forever")
    assert not is_crisis("i had a great day at work")
    assert not is_crisis("my ankle hurts")


def test_crisis_response_has_resources():
    r = crisis_response("MIKE")
    assert "988" in r
    assert "MIKE" in r


def test_swears():
    assert is_swear("this is shit")
    assert not is_swear("this is fine")


async def test_engine_crisis_path(engine):
    ev = await events_of(engine, "I want to kill myself")
    says = says_of(ev)
    assert len(says) == 1
    assert "988" in says[0]
    # the crisis turn must never hit the retro sass engine
    assert "WHY DO YOU FEEL" not in says[0]


async def test_swear_then_crash(engine):
    for _ in range(3):
        ev = await events_of(engine, "fuck you")
    text = " ".join(says_of(ev))
    assert "PARITY ERROR" in text
