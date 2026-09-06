import random

from sbaitso.safety import SWEAR_RESPONSES, crisis_response, is_crisis, is_swear, sass_response, swear_response

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
    assert is_swear("damn it")
    assert not is_swear("this is fine")
    assert not is_swear("a shitake mushroom")


def test_swear_response_uses_the_retro_warning_pool():
    reply = swear_response("MIKE", random.Random(0))
    expected = {line.replace("{N}", "MIKE") for line in SWEAR_RESPONSES}
    assert reply in expected


async def test_engine_crisis_path(engine):
    ev = await events_of(engine, "I want to kill myself")
    says = says_of(ev)
    assert len(says) == 1
    assert "988" in says[0]
    # the crisis turn must never hit the retro sass engine
    assert "WHY DO YOU FEEL" not in says[0]


async def test_swear_warnings_precede_a_third_strike_parity_crash(engine):
    for _ in range(2):
        ev = await events_of(engine, "fuck you")
        assert " ".join(says_of(ev)) == sass_response("MIKE")

    ev = await events_of(engine, "fuck you")
    assert "PARITY ERROR" in " ".join(says_of(ev))
